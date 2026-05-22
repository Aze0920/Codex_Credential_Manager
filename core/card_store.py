# -*- coding: utf-8 -*-
"""卡密与账号池存储（SQLite）。"""
from __future__ import annotations

import json
import queue
import re
import secrets
import sqlite3
import string
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from core.db_config import get_database_path
from core.activity_logger import log_activity, log_exception
from core.account_parser import parse_account_import, parse_bulk_oauth_material, parse_material_line
from core.account_quota import query_chatgpt_quota
from core.account_tester import (
    DEFAULT_TEST_MESSAGE,
    DEFAULT_TEST_MODEL,
    normalize_test_model,
    test_chatgpt_oauth,
)
from core.openai_oauth import (
    CODEX_CLIENT_ID,
    MOBILE_CLIENT_ID,
    access_token_is_valid,
    ensure_fresh_oauth,
    exchange_authorization_code,
    parse_authorization_input,
    parse_codex_import_entries,
    refresh_access_token,
    token_info_to_pool_record,
)

DB_PATH = get_database_path()
LOCK = threading.RLock()
IMPORT_MAX_CONCURRENCY = 5
_PROVISION_EXECUTOR: ThreadPoolExecutor | None = None
_PROVISION_EXECUTOR_LOCK = threading.Lock()


def _get_provision_executor() -> ThreadPoolExecutor:
    global _PROVISION_EXECUTOR
    with _PROVISION_EXECUTOR_LOCK:
        if _PROVISION_EXECUTOR is None:
            _PROVISION_EXECUTOR = ThreadPoolExecutor(
                max_workers=IMPORT_MAX_CONCURRENCY,
                thread_name_prefix="provision",
            )
        return _PROVISION_EXECUTOR

CARD_LEGACY_PREFIX = "Codex-"
CARD_LEGACY_SUFFIX_LEN = 16
CARD_POOL_CONFIG: dict[str, dict[str, Any]] = {
    "pp": {"prefix": "Codex-P", "suffix_len": 20, "label": "PP"},
    "go": {"prefix": "Codex-G", "suffix_len": 20, "label": "GO"},
}
CARD_LEGACY_PATTERN = re.compile(
    rf"^{re.escape(CARD_LEGACY_PREFIX)}[A-Za-z0-9]{{{CARD_LEGACY_SUFFIX_LEN}}}$"
)
PAGE_SIZE_OPTIONS = (10, 50, 100, 500, 1000, 5000)


def normalize_pool_type(value: str | None) -> str:
    normalized = (value or "pp").strip().lower()
    if normalized in {"go", "gopay", "g"}:
        return "go"
    return "pp"


def pool_type_label(pool_type: str | None) -> str:
    key = normalize_pool_type(pool_type)
    return str(CARD_POOL_CONFIG[key]["label"])


def parse_card_code(value: str) -> tuple[str, str]:
    code = (value or "").strip()
    if not code:
        raise ValueError("卡密不能为空")
    for pool_type, cfg in CARD_POOL_CONFIG.items():
        prefix = str(cfg["prefix"])
        suffix_len = int(cfg["suffix_len"])
        pattern = re.compile(rf"^{re.escape(prefix)}[A-Za-z0-9]{{{suffix_len}}}$")
        if pattern.fullmatch(code):
            return code, pool_type
    if CARD_LEGACY_PATTERN.fullmatch(code):
        return code, "pp"
    raise ValueError("卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位（旧版 Codex- + 16 位仍可用）")


def is_valid_card_code(value: str) -> bool:
    try:
        parse_card_code(value)
        return True
    except ValueError:
        return False


def normalize_card_code(value: str) -> str:
    code, _pool_type = parse_card_code(value)
    return code


def generate_card_code(conn: sqlite3.Connection, pool_type: str) -> str:
    normalized_pool = normalize_pool_type(pool_type)
    cfg = CARD_POOL_CONFIG[normalized_pool]
    prefix = str(cfg["prefix"])
    suffix_len = int(cfg["suffix_len"])
    alphabet = string.ascii_letters + string.digits
    for _ in range(200):
        suffix = "".join(secrets.choice(alphabet) for _ in range(suffix_len))
        code = f"{prefix}{suffix}"
        row = conn.execute("SELECT 1 FROM card_keys WHERE code = ?", (code,)).fetchone()
        if not row:
            return code
    raise RuntimeError("无法生成唯一卡密，请稍后重试")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.OperationalError:
        pass


def _migrate_pool_accounts(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(pool_accounts)")}
    migrations = (
        ("account_type", "TEXT NOT NULL DEFAULT 'email'"),
        ("oauth_data", "TEXT NOT NULL DEFAULT ''"),
        ("test_status", "TEXT"),
        ("test_result", "TEXT"),
        ("last_test_at", "TEXT"),
        ("quota_data", "TEXT"),
        ("quota_updated_at", "TEXT"),
        ("group_name", "TEXT NOT NULL DEFAULT ''"),
        ("assigned_proxy", "TEXT NOT NULL DEFAULT ''"),
        ("mailbox_material", "TEXT NOT NULL DEFAULT ''"),
        ("pool_type", "TEXT NOT NULL DEFAULT 'pp'"),
        ("remark", "TEXT NOT NULL DEFAULT ''"),
        ("priority_sale", "INTEGER NOT NULL DEFAULT 0"),
        ("priority_sale_at", "TEXT"),
    )
    for name, typedef in migrations:
        if name not in columns:
            conn.execute(f"ALTER TABLE pool_accounts ADD COLUMN {name} {typedef}")
    if "assigned_proxy" not in columns:
        _backfill_assigned_proxies(conn)


def _migrate_card_keys(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(card_keys)")}
    if "pool_type" not in columns:
        conn.execute("ALTER TABLE card_keys ADD COLUMN pool_type TEXT NOT NULL DEFAULT 'pp'")


def _backfill_assigned_proxies(conn: sqlite3.Connection) -> None:
    raw = conn.execute("SELECT value FROM app_settings WHERE key = 'proxy_pool'").fetchone()
    if not raw:
        return
    try:
        pool_data = json.loads(raw["value"])
    except json.JSONDecodeError:
        return
    if not isinstance(pool_data, list):
        return
    pool = [str(item).strip() for item in pool_data if str(item).strip()]
    if not pool:
        return
    rows = conn.execute(
        """
        SELECT id FROM pool_accounts
        WHERE coalesce(assigned_proxy, '') = ''
        ORDER BY created_at ASC
        """
    ).fetchall()
    for index, row in enumerate(rows):
        conn.execute(
            "UPDATE pool_accounts SET assigned_proxy = ? WHERE id = ?",
            (pool[index % len(pool)], row["id"]),
        )


def backfill_empty_account_proxies() -> int:
    updated = 0
    with LOCK:
        conn = _connect()
        try:
            raw = conn.execute("SELECT value FROM app_settings WHERE key = 'proxy_pool'").fetchone()
            if not raw:
                return 0
            try:
                pool_data = json.loads(raw["value"])
            except json.JSONDecodeError:
                return 0
            if not isinstance(pool_data, list):
                return 0
            pool = [str(item).strip() for item in pool_data if str(item).strip()]
            if not pool:
                return 0
            rows = conn.execute(
                """
                SELECT id FROM pool_accounts
                WHERE coalesce(assigned_proxy, '') = ''
                ORDER BY created_at ASC
                """
            ).fetchall()
            for index, row in enumerate(rows):
                conn.execute(
                    "UPDATE pool_accounts SET assigned_proxy = ? WHERE id = ?",
                    (pool[index % len(pool)], row["id"]),
                )
                updated += 1
            conn.commit()
            return updated
        finally:
            conn.close()


def get_setting(key: str) -> str | None:
    with LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
            return str(row["value"]) if row else None
        finally:
            conn.close()


def set_setting(key: str, value: str) -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                (key, value),
            )
            conn.commit()
        finally:
            conn.close()


def delete_setting(key: str) -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            conn.commit()
        finally:
            conn.close()


def get_setting_json(key: str) -> Any:
    raw = get_setting(key)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def set_setting_json(key: str, value: Any) -> None:
    set_setting(key, json.dumps(value, ensure_ascii=False))


def normalize_group_name(value: str | None, *, account_type: str = "email") -> str:
    group = (value or "").strip().lower()
    if group in {"outlook", "email", "邮箱"}:
        return "outlook"
    if group in {"oauth", "chatgpt_oauth", "chatgpt-oauth"}:
        return "oauth"
    if group:
        return group
    normalized_type = (account_type or "email").strip().lower()
    return "oauth" if normalized_type == "oauth" else "outlook"


def init_db() -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS pool_accounts (
                    id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    material TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'available',
                    card_code TEXT,
                    created_at TEXT NOT NULL,
                    assigned_at TEXT
                );
                CREATE TABLE IF NOT EXISTS card_keys (
                    id TEXT PRIMARY KEY,
                    code TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'available',
                    account_id TEXT,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    FOREIGN KEY(account_id) REFERENCES pool_accounts(id)
                );
                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pool_accounts_status ON pool_accounts(status);
                CREATE INDEX IF NOT EXISTS idx_card_keys_status ON card_keys(status);
                """
            )
            _migrate_pool_accounts(conn)
            _migrate_card_keys(conn)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pool_accounts_group ON pool_accounts(group_name)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_pool_accounts_pool_type ON pool_accounts(pool_type)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_card_keys_pool_type ON card_keys(pool_type)"
            )
            conn.execute(
                """
                UPDATE pool_accounts
                SET group_name = CASE
                    WHEN lower(coalesce(account_type, 'email')) = 'oauth' THEN 'oauth'
                    ELSE 'outlook'
                END
                WHERE coalesce(group_name, '') = ''
                """
            )
            conn.commit()
        finally:
            conn.close()


def normalize_page(value: Any) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def normalize_page_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = 10
    if size not in PAGE_SIZE_OPTIONS:
        allowed = ", ".join(str(item) for item in PAGE_SIZE_OPTIONS)
        raise ValueError(f"每页条数只能是 {allowed}")
    return size


def _paginate(total: int, page: int, page_size: int) -> dict[str, int]:
    total_pages = max(1, (total + page_size - 1) // page_size) if total else 1
    page = min(page, total_pages)
    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
        "offset": (page - 1) * page_size,
    }


def add_pool_accounts(records: list[dict[str, str]], *, pool_type: str = "pp") -> tuple[int, int, list[str]]:
    from core.app_settings import get_proxy_pool

    imported = 0
    skipped = 0
    inserted_ids: list[str] = []
    now = now_iso()
    proxy_pool = get_proxy_pool()
    proxy_index = 0
    normalized_pool = normalize_pool_type(pool_type)
    with LOCK:
        conn = _connect()
        try:
            for item in records:
                email = (item.get("email") or "").strip()
                if not email:
                    skipped += 1
                    continue
                existing = conn.execute(
                    "SELECT id, assigned_proxy FROM pool_accounts WHERE email = ? COLLATE NOCASE",
                    (email,),
                ).fetchone()
                if existing:
                    existing_id = str(existing["id"])
                    account_type = (item.get("account_type") or "email").strip().lower() or "email"
                    group_name = normalize_group_name(item.get("group_name"), account_type=account_type)
                    assigned_proxy = str(item.get("assigned_proxy") or "").strip()
                    if not assigned_proxy:
                        assigned_proxy = str(existing["assigned_proxy"] or "").strip()
                    if not assigned_proxy and proxy_pool:
                        assigned_proxy = proxy_pool[proxy_index % len(proxy_pool)]
                        proxy_index += 1
                    remark = str(item.get("remark") or "").strip()
                    conn.execute(
                        """
                        UPDATE pool_accounts
                        SET password = ?, client_id = ?, refresh_token = ?, material = ?,
                            account_type = ?, oauth_data = '', group_name = ?,
                            assigned_proxy = CASE WHEN ? != '' THEN ? ELSE assigned_proxy END,
                            quota_data = '', quota_updated_at = NULL,
                            test_status = 'pending',
                            test_result = ?,
                            last_test_at = NULL,
                            remark = CASE WHEN ? != '' THEN ? ELSE remark END
                        WHERE id = ?
                        """,
                        (
                            item.get("password") or "",
                            item.get("client_id") or "",
                            item.get("refresh_token") or "",
                            item.get("material") or "",
                            account_type,
                            group_name,
                            assigned_proxy,
                            assigned_proxy,
                            json.dumps({"ok": False, "message": "等待检测"}, ensure_ascii=False),
                            remark,
                            remark,
                            existing_id,
                        ),
                    )
                    imported += 1
                    inserted_ids.append(existing_id)
                    continue
                row_id = secrets.token_urlsafe(8)
                account_type = (item.get("account_type") or "email").strip().lower() or "email"
                group_name = normalize_group_name(item.get("group_name"), account_type=account_type)
                assigned_proxy = str(item.get("assigned_proxy") or "").strip()
                if not assigned_proxy and proxy_pool:
                    assigned_proxy = proxy_pool[proxy_index % len(proxy_pool)]
                    proxy_index += 1
                remark = str(item.get("remark") or "").strip()
                conn.execute(
                    """
                    INSERT INTO pool_accounts (
                        id, email, password, client_id, refresh_token, material,
                        account_type, oauth_data, group_name, assigned_proxy, pool_type, remark, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'available', ?)
                    """,
                    (
                        row_id,
                        email,
                        item.get("password") or "",
                        item.get("client_id") or "",
                        item.get("refresh_token") or "",
                        item.get("material") or "",
                        account_type,
                        item.get("oauth_data") or "",
                        group_name,
                        assigned_proxy,
                        normalized_pool,
                        remark,
                        now,
                    ),
                )
                imported += 1
                inserted_ids.append(row_id)
            conn.commit()
        finally:
            conn.close()
    return imported, skipped, inserted_ids


def _parse_import_records(
    material: str,
    account_type: str,
    *,
    oauth_method: str = "codex_json",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
) -> tuple[list[dict[str, Any]], int, str]:
    normalized_type = (account_type or "email").strip().lower()
    if normalized_type in {"oauth", "chatgpt_oauth", "chatgpt-oauth"}:
        method = (oauth_method or "codex_json").strip().lower()
        if method == "manual":
            code, parsed_state = parse_authorization_input(auth_input or material)
            token_info = exchange_authorization_code(
                session_id=session_id,
                code=code,
                state=state or parsed_state,
            )
            records = [token_info_to_pool_record(token_info)]
            parse_skipped = 0
        elif method in {"rt", "refresh_token"}:
            records, parse_skipped = _records_from_refresh_tokens(material, client_id=CODEX_CLIENT_ID)
        elif method in {"mobile_rt", "mobile"}:
            records, parse_skipped = _records_from_refresh_tokens(material, client_id=MOBILE_CLIENT_ID)
        elif method in {"codex_json", "codex", "json", "at"}:
            try:
                records = parse_codex_import_entries(material)
                parse_skipped = 0
            except ValueError:
                records, parse_skipped = parse_bulk_oauth_material(material)
        else:
            raise ValueError("不支持的 OAuth 导入方式")
    else:
        records, parse_skipped = parse_account_import(material, account_type)
    default_group = normalize_group_name(
        normalized_type if normalized_type in {"oauth", "chatgpt_oauth", "chatgpt-oauth"} else "outlook",
        account_type=normalized_type,
    )
    for record in records:
        record["group_name"] = normalize_group_name(
            record.get("group_name") or default_group,
            account_type=record.get("account_type") or normalized_type,
        )
    return records, parse_skipped, normalized_type


def _apply_import_remark(records: list[dict[str, Any]], remark: str | None) -> None:
    text = str(remark or "").strip()
    if not text:
        return
    for record in records:
        if not str(record.get("remark") or "").strip():
            record["remark"] = text


def _build_provision_detail(
    *,
    account_id: str,
    email: str,
    account_type: str,
    test_status: str,
    result: dict[str, Any],
    quota: dict[str, Any] | None = None,
    ok: bool | None = None,
    error: str = "",
) -> dict[str, Any]:
    quota_data = quota if isinstance(quota, dict) else {}
    if ok is None:
        ok = test_status == "success" and bool(result.get("ok"))
    return {
        "ok": ok,
        "accountId": account_id,
        "email": email,
        "accountType": account_type,
        "testStatus": test_status,
        "loginMode": result.get("loginMode"),
        "loginMs": result.get("loginMs"),
        "quotaMs": result.get("quotaMs"),
        "testMs": result.get("latencyMs"),
        "totalMs": result.get("totalMs"),
        "planType": str(quota_data.get("planType") or "").strip(),
        "quotaSummary": str(quota_data.get("summary") or "").strip(),
        "model": result.get("model"),
        "reply": str(result.get("reply") or "")[:120],
        "error": error or result.get("error"),
        "quota": quota_data,
        "result": result,
    }


def provision_pool_account_steps(
    account_id: str,
    *,
    model: str | None = None,
    message: str | None = None,
) -> Iterator[dict[str, Any]]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    account_type = (row["account_type"] or "email").strip().lower()
    try:
        from core.app_settings import get_test_settings

        test_defaults = get_test_settings()
        default_model = test_defaults["defaultModel"]
        default_message = test_defaults["defaultMessage"]
        allowed_models = tuple(test_defaults["models"])
    except Exception:
        default_model = DEFAULT_TEST_MODEL
        default_message = DEFAULT_TEST_MESSAGE
        allowed_models = None
    test_model = normalize_test_model(model or default_model, allowed=allowed_models)
    test_message = (message or default_message).strip() or default_message
    email = row["email"]
    provision_started = time.time()

    log_activity(
        category="provision",
        action="provision.start",
        message=f"开始初始化账号 {email}",
        account_id=account_id,
        email=email,
        status="running",
        detail={
            "accountType": account_type,
            "model": test_model,
            "message": test_message,
        },
    )

    yield {"step": "login", "message": "正在登录..."}
    try:
        credentials = _resolve_pool_account_credentials(row)
        access_token = credentials["accessToken"]
        chatgpt_account_id = credentials["chatgptAccountId"]
        account_proxy = credentials.get("proxy", _account_proxy(row))
        log_activity(
            category="login",
            action="provision.login",
            message=f"{email} 登录成功 ({credentials.get('loginMode')})",
            account_id=account_id,
            email=email,
            status="success",
            duration_ms=credentials.get("loginMs"),
            detail=credentials,
        )

        yield {"step": "quota", "message": "正在查询额度..."}
        quota_started = time.time()
        try:
            quota = query_chatgpt_quota(
                access_token,
                chatgpt_account_id=chatgpt_account_id,
                proxy=account_proxy,
            )
            quota_ms = int((time.time() - quota_started) * 1000)
            update_account_quota(account_id, quota)
            log_activity(
                category="quota",
                action="provision.quota",
                message=f"{email} 额度: {quota.get('summary') or quota.get('planType') or '已查询'}",
                account_id=account_id,
                email=email,
                status="success" if quota.get("ok", True) else "failed",
                duration_ms=quota_ms,
                detail=quota,
            )
        except Exception as exc:
            quota = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
            quota_ms = int((time.time() - quota_started) * 1000)
            log_exception(
                category="quota",
                action="provision.quota",
                message=f"{email} 额度查询失败",
                exc=exc,
                account_id=account_id,
                email=email,
                duration_ms=quota_ms,
                detail=quota,
            )

        yield {"step": "test", "message": f"正在测试模型 {test_model}..."}
        result = test_chatgpt_oauth(
            access_token,
            chatgpt_account_id=chatgpt_account_id,
            model=test_model,
            message=test_message,
            proxy=account_proxy,
        )
        result["loginMs"] = credentials.get("loginMs")
        result["loginMode"] = credentials.get("loginMode")
        result["proxy"] = account_proxy
        result["proxyLabel"] = credentials.get("proxyLabel") or _proxy_label(account_proxy)
        if credentials.get("loginMode") == "email_login":
            result["login"] = "ok"
        result["quota"] = quota
        result["quotaMs"] = quota_ms
        result["totalMs"] = int(
            (result.get("loginMs") or 0) + (result.get("latencyMs") or 0) + quota_ms
        )

        quota_ok = _quota_is_healthy(quota if isinstance(quota, dict) else None)
        status = "success" if result.get("ok") and quota_ok else "failed"
        if not quota_ok:
            result["ok"] = False
            result["error"] = str(
                result.get("error") or (quota.get("error") if isinstance(quota, dict) else "") or "额度查询失败"
            ).strip()
        update_account_test(account_id, status=status, result=result)
        detail = _build_provision_detail(
            account_id=account_id,
            email=email,
            account_type=account_type,
            test_status=status,
            result=result,
            quota=quota if isinstance(quota, dict) else None,
        )
        log_activity(
            level="info" if status == "success" else "warn",
            category="test",
            action="provision.test",
            message=f"{email} 模型测试 {status}: {test_model}",
            account_id=account_id,
            email=email,
            status=status,
            duration_ms=int((time.time() - provision_started) * 1000),
            detail={"provision": detail, "result": result, "quota": quota},
        )
        yield {"step": "done", "detail": detail, "testStatus": status, "result": result}
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}".strip(": ")
        if isinstance(exc, NotImplementedError):
            error_text = "测试引擎版本过旧，请重启服务后再试（NotImplementedError）"
        login_ms = 0
        result = {
            "ok": False,
            "model": test_model,
            "message": test_message,
            "error": error_text,
            "reply": "",
        }
        update_account_test(account_id, status="failed", result=result)
        detail = _build_provision_detail(
            account_id=account_id,
            email=email,
            account_type=account_type,
            test_status="failed",
            result=result,
            quota=None,
            ok=False,
            error=error_text,
        )
        log_exception(
            category="provision",
            action="provision.failed",
            message=f"{email} 初始化失败",
            exc=exc,
            account_id=account_id,
            email=email,
            duration_ms=int((time.time() - provision_started) * 1000),
            detail={"provision": detail, "result": result},
        )
        yield {"step": "done", "detail": detail, "testStatus": "failed", "result": result}


def _enqueue_provision_account(
    account_id: str,
    *,
    index: int,
    total: int,
    event_queue: queue.Queue,
) -> None:
    row = get_pool_account(account_id)
    email = row["email"] if row else account_id
    detail: dict[str, Any] | None = None
    try:
        event_queue.put(
            {
                "type": "account_start",
                "index": index,
                "total": total,
                "email": email,
                "message": f"[{index}/{total}] {email} — 开始处理",
            }
        )
        for event in provision_pool_account_steps(account_id):
            step = event.get("step")
            if step == "done":
                detail = event.get("detail") or {}
                event_queue.put(
                    {
                        "type": "account_done",
                        "index": index,
                        "total": total,
                        "email": email,
                        "detail": detail,
                    }
                )
            else:
                event_queue.put(
                    {
                        "type": "step",
                        "index": index,
                        "total": total,
                        "email": email,
                        "step": step,
                        "message": event.get("message") or "",
                    }
                )
    finally:
        event_queue.put({"type": "_worker_done", "index": index, "detail": detail})


def iter_import_pool_accounts(
    material: str,
    account_type: str,
    *,
    oauth_method: str = "codex_json",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
    pool_type: str = "pp",
    remark: str = "",
) -> Iterator[dict[str, Any]]:
    yield {"type": "phase", "message": "正在解析账号..."}
    try:
        records, parse_skipped, _normalized_type = _parse_import_records(
            material,
            account_type,
            oauth_method=oauth_method,
            session_id=session_id,
            auth_input=auth_input,
            state=state,
        )
    except ValueError as exc:
        yield {"type": "error", "error": str(exc)}
        return

    _apply_import_remark(records, remark)

    yield {"type": "phase", "message": f"正在写入数据库，共 {len(records)} 个账号..."}
    imported, db_skipped, inserted_ids = add_pool_accounts(records, pool_type=pool_type)
    skipped = parse_skipped + db_skipped
    total = len(inserted_ids)

    yield {
        "type": "parsed",
        "imported": imported,
        "skipped": skipped,
        "parsed": len(records),
        "pending": total,
    }

    if total <= 0:
        yield {
            "type": "done",
            "imported": imported,
            "skipped": skipped,
            "parsed": len(records),
            "activated": 0,
            "failed": 0,
            "details": [],
        }
        return

    max_workers = min(IMPORT_MAX_CONCURRENCY, total)
    yield {
        "type": "phase",
        "message": f"并行处理 {total} 个账号（最多 {max_workers} 个同时进行）...",
    }

    event_queue: queue.Queue = queue.Queue()
    details_map: dict[int, dict[str, Any] | None] = {}
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(_enqueue_provision_account, account_id, index=index, total=total, event_queue=event_queue)
            for index, account_id in enumerate(inserted_ids, start=1)
        ]
        while completed < total:
            event = event_queue.get()
            if event.get("type") == "_worker_done":
                details_map[int(event["index"])] = event.get("detail")
                completed += 1
                continue
            yield event
        for future in futures:
            future.result()

    details: list[dict[str, Any]] = []
    for index in range(1, total + 1):
        item = details_map.get(index)
        if isinstance(item, dict):
            details.append(item)
        else:
            row = get_pool_account(inserted_ids[index - 1])
            details.append(
                {
                    "ok": False,
                    "email": row["email"] if row else inserted_ids[index - 1],
                    "error": "处理未完成",
                }
            )
    activated = sum(1 for item in details if item.get("ok"))
    failed = len(details) - activated

    log_activity(
        category="import",
        action="import.completed",
        message=f"导入完成: 新增 {imported}, 跳过 {skipped}, 通过 {activated}, 失败 {failed}",
        status="success" if failed == 0 else "failed",
        detail={
            "imported": imported,
            "skipped": skipped,
            "parsed": len(records),
            "activated": activated,
            "failed": failed,
            "accountType": account_type,
            "oauthMethod": oauth_method,
            "details": details,
        },
    )

    yield {
        "type": "done",
        "imported": imported,
        "skipped": skipped,
        "parsed": len(records),
        "activated": activated,
        "failed": failed,
        "details": details,
    }


def import_pool_accounts(
    material: str,
    account_type: str,
    *,
    oauth_method: str = "codex_json",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
    pool_type: str = "pp",
    remark: str = "",
) -> dict[str, Any]:
    summary: dict[str, Any] | None = None
    for event in iter_import_pool_accounts(
        material,
        account_type,
        oauth_method=oauth_method,
        session_id=session_id,
        auth_input=auth_input,
        state=state,
        pool_type=pool_type,
        remark=remark,
    ):
        if event.get("type") == "done":
            summary = event
        elif event.get("type") == "error":
            raise ValueError(str(event.get("error") or "导入失败"))
    if not summary:
        raise ValueError("导入失败")
    return {
        "imported": summary.get("imported", 0),
        "skipped": summary.get("skipped", 0),
        "parsed": summary.get("parsed", 0),
        "activated": summary.get("activated", 0),
        "failed": summary.get("failed", 0),
        "details": summary.get("details") or [],
    }


def _mark_account_pending(account_id: str) -> None:
    update_account_test(
        account_id,
        status="pending",
        result={"ok": False, "message": "等待检测"},
    )


def _run_background_provision(account_id: str) -> None:
    update_account_test(
        account_id,
        status="running",
        result={"ok": False, "message": "后台检测中"},
    )
    try:
        for event in provision_pool_account_steps(account_id):
            if event.get("step") == "done":
                return
    except Exception as exc:
        error_text = f"{type(exc).__name__}: {exc}".strip(": ")
        update_account_test(
            account_id,
            status="failed",
            result={"ok": False, "error": error_text},
        )


def enqueue_provision_accounts(account_ids: list[str]) -> None:
    if not account_ids:
        return
    executor = _get_provision_executor()
    for account_id in account_ids:
        _mark_account_pending(account_id)
        executor.submit(_run_background_provision, account_id)


def import_pool_accounts_background(
    material: str,
    account_type: str,
    *,
    oauth_method: str = "codex_json",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
    pool_type: str = "pp",
    remark: str = "",
) -> dict[str, Any]:
    records, parse_skipped, _normalized_type = _parse_import_records(
        material,
        account_type,
        oauth_method=oauth_method,
        session_id=session_id,
        auth_input=auth_input,
        state=state,
    )
    _apply_import_remark(records, remark)
    imported, db_skipped, inserted_ids = add_pool_accounts(records, pool_type=pool_type)
    enqueue_provision_accounts(inserted_ids)
    return {
        "imported": imported,
        "skipped": parse_skipped + db_skipped,
        "parsed": len(records),
        "queued": len(inserted_ids),
        "background": True,
        "accountIds": inserted_ids,
    }


def _records_from_refresh_tokens(content: str, *, client_id: str) -> tuple[list[dict[str, str]], int]:
    tokens = [line.strip() for line in (content or "").splitlines() if line.strip() and not line.strip().startswith("#")]
    if not tokens:
        raise ValueError("请输入至少一个 refresh_token")
    records: list[dict[str, str]] = []
    skipped = 0
    for token in tokens:
        try:
            info = refresh_access_token(token, client_id=client_id)
            records.append(token_info_to_pool_record(info))
        except Exception:
            skipped += 1
    if not records:
        raise ValueError("所有 refresh_token 刷新失败，请检查令牌是否有效")
    return records, skipped


def update_account_quota(account_id: str, quota: dict[str, Any]) -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE pool_accounts
                SET quota_data = ?, quota_updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(quota, ensure_ascii=False), now_iso(), account_id),
            )
            conn.commit()
        finally:
            conn.close()


def _parse_quota_data(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _parse_test_result(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _quota_is_healthy(quota: dict[str, Any] | None) -> bool:
    if not isinstance(quota, dict) or not quota:
        return True
    return bool(quota.get("ok", True))


def _merge_abnormal_test_result(
    row: sqlite3.Row | None,
    *,
    quota: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    result = _parse_test_result(row["test_result"] if row and "test_result" in row.keys() else "")
    if isinstance(quota, dict):
        result["quota"] = quota
    message = str(error or (quota or {}).get("error") or "额度查询失败").strip()
    result["ok"] = False
    result["error"] = message
    return result


def _mark_account_abnormal(account_id: str, *, quota: dict[str, Any] | None = None, error: str = "") -> None:
    row = get_pool_account(account_id)
    if not row:
        return
    result = _merge_abnormal_test_result(row, quota=quota, error=error)
    update_account_test(account_id, status="failed", result=result)


def _account_counts_as_failed(test_status: str | None, quota_data: str | None) -> bool:
    if str(test_status or "").strip().lower() == "failed":
        return True
    quota = _parse_quota_data(quota_data)
    return isinstance(quota, dict) and quota.get("ok") is False


def _session_info_to_oauth_data(session_info: dict[str, Any], *, email: str = "") -> dict[str, Any]:
    user = session_info.get("user") if isinstance(session_info.get("user"), dict) else {}
    account = session_info.get("account") if isinstance(session_info.get("account"), dict) else {}
    data: dict[str, Any] = {
        "access_token": str(session_info.get("accessToken") or "").strip(),
        "chatgpt_account_id": str(account.get("id") or "").strip(),
        "chatgpt_user_id": str(user.get("id") or "").strip(),
        "email": str(user.get("email") or email or "").strip(),
        "plan_type": str(account.get("planType") or "").strip(),
        "source": "email_login",
        "cached_at": now_iso(),
        "expires": str(session_info.get("expires") or "").strip(),
    }
    session_token = str(session_info.get("sessionToken") or "").strip()
    if session_token:
        data["session_token"] = session_token
    return data


def activate_pool_account(account_id: str) -> dict[str, Any]:
    """导入后自动登录、查额度并测试模型。"""
    detail: dict[str, Any] | None = None
    for event in provision_pool_account_steps(account_id):
        if event.get("step") == "done":
            detail = event.get("detail")
    if not detail:
        raise ValueError("账号初始化失败")
    return detail


def _persist_oauth_data(account_id: str, oauth: dict[str, Any]) -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE pool_accounts SET oauth_data = ? WHERE id = ?",
                (json.dumps(oauth, ensure_ascii=False), account_id),
            )
            conn.commit()
        finally:
            conn.close()


def _email_session_cache(oauth: dict[str, Any]) -> tuple[str, str] | None:
    access_token = str(oauth.get("access_token") or "").strip()
    chatgpt_account_id = str(oauth.get("chatgpt_account_id") or "").strip()
    if not access_token or not chatgpt_account_id:
        return None
    if not access_token_is_valid(access_token):
        return None
    return access_token, chatgpt_account_id


def account_has_mailbox(row: sqlite3.Row) -> bool:
    account_type = ((row["account_type"] if "account_type" in row.keys() else "") or "email").strip().lower()
    if account_type == "oauth":
        mailbox_material = str(row["mailbox_material"] if "mailbox_material" in row.keys() else "").strip()
        return bool(mailbox_material)
    client_id = str(row["client_id"] if "client_id" in row.keys() else "").strip()
    refresh_token = str(row["refresh_token"] if "refresh_token" in row.keys() else "").strip()
    return bool(client_id and refresh_token)


def outlook_account_from_row(row: sqlite3.Row):
    from core.account_parser import parse_material_line
    from core.outlook_client import OutlookAccount

    account_type = ((row["account_type"] if "account_type" in row.keys() else "") or "email").strip().lower()
    if account_type == "oauth":
        mailbox_material = str(row["mailbox_material"] if "mailbox_material" in row.keys() else "").strip()
        if not mailbox_material:
            raise ValueError("该 OAuth 账号尚未绑定 Outlook 邮箱，请先添加邮箱凭证")
        account = parse_material_line(mailbox_material)
        pool_email = str(row["email"] or "").strip().lower()
        if account.email.strip().lower() != pool_email:
            raise ValueError(f"邮箱素材与账号不一致：素材为 {account.email}，账号为 {row['email']}")
        return account

    client_id = str(row["client_id"] or "").strip()
    refresh_token = str(row["refresh_token"] or "").strip()
    if not client_id or not refresh_token:
        raise ValueError("该账号缺少 Outlook 邮箱凭证，无法读取验证码")
    return OutlookAccount(
        email=str(row["email"] or "").strip(),
        password=str(row["password"] or "").strip(),
        client_id=client_id,
        refresh_token=refresh_token,
    )


def link_mailbox_to_oauth_account(account_id: str, material: str) -> dict[str, Any]:
    from core.account_parser import parse_material_line

    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    account_type = (row["account_type"] or "email").strip().lower()
    if account_type != "oauth":
        raise ValueError("仅 OAuth 账号支持额外绑定 Outlook 邮箱")

    text = str(material or "").strip()
    if not text:
        raise ValueError("请粘贴邮箱素材：email----password----clientId----refreshToken")
    account = parse_material_line(text.splitlines()[0] if "\n" in text else text)
    pool_email = str(row["email"] or "").strip().lower()
    if account.email.strip().lower() != pool_email:
        raise ValueError(f"邮箱素材必须与账号邮箱一致（当前账号：{row['email']}）")

    mailbox_material = "----".join([account.email, account.password, account.client_id, account.refresh_token])
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE pool_accounts SET mailbox_material = ? WHERE id = ?",
                (mailbox_material, account_id),
            )
            conn.commit()
        finally:
            conn.close()

    payload = {
        "accountId": account_id,
        "email": row["email"],
        "hasMailbox": True,
        "mailboxEmail": account.email,
    }
    log_activity(
        category="settings",
        action="account.mailbox_link",
        message=f"OAuth 账号 {row['email']} 已绑定 Outlook 邮箱",
        account_id=account_id,
        email=row["email"],
        status="success",
        detail={"mailboxEmail": account.email, "clientId": account.client_id},
    )
    return payload


def _account_proxy(row: sqlite3.Row) -> str:
    if "assigned_proxy" not in row.keys():
        return ""
    return str(row["assigned_proxy"] or "").strip()


def _proxy_label(proxy: str) -> str:
    from core.proxy_tester import mask_proxy

    return mask_proxy(proxy) if proxy else "直连"


def update_pool_account_proxy(account_id: str, proxy: str | None) -> dict[str, Any]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    assigned_proxy = str(proxy or "").strip()
    pool = []
    try:
        from core.app_settings import get_proxy_pool

        pool = get_proxy_pool()
    except Exception:
        pool = []
    if assigned_proxy and pool and assigned_proxy not in pool:
        current = _account_proxy(row)
        if assigned_proxy != current:
            raise ValueError("所选代理不在当前代理池中，请先在设置里保存代理池")
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE pool_accounts SET assigned_proxy = ? WHERE id = ?",
                (assigned_proxy, account_id),
            )
            conn.commit()
        finally:
            conn.close()
    payload = {
        "accountId": account_id,
        "email": row["email"],
        "assignedProxy": assigned_proxy,
        "proxyLabel": _proxy_label(assigned_proxy),
    }
    log_activity(
        category="settings",
        action="account.proxy",
        message=f"{row['email']} 代理已设为 {payload['proxyLabel']}",
        account_id=account_id,
        email=row["email"],
        status="success",
        detail=payload,
    )
    return payload


def _resolve_pool_account_credentials(row: sqlite3.Row, *, force_login: bool = False) -> dict[str, Any]:
    account_id = row["id"]
    account_type = (row["account_type"] or "email").strip().lower()
    started = time.time()
    proxy = _account_proxy(row)

    if account_type == "oauth":
        oauth = ensure_fresh_oauth(oauth_data_dict(row), proxy=proxy)
        if oauth != oauth_data_dict(row):
            _persist_oauth_data(account_id, oauth)
        access_token = str(oauth.get("access_token") or "").strip()
        chatgpt_account_id = str(oauth.get("chatgpt_account_id") or "").strip()
        if not access_token:
            raise ValueError("OAuth 账号缺少 access_token")
        return {
            "accessToken": access_token,
            "chatgptAccountId": chatgpt_account_id,
            "loginMs": int((time.time() - started) * 1000),
            "loginMode": "oauth",
            "proxy": proxy,
            "proxyLabel": _proxy_label(proxy),
        }

    cached = None if force_login else _email_session_cache(oauth_data_dict(row))
    if cached:
        access_token, chatgpt_account_id = cached
        return {
            "accessToken": access_token,
            "chatgptAccountId": chatgpt_account_id,
            "loginMs": int((time.time() - started) * 1000),
            "loginMode": "cache",
            "proxy": proxy,
            "proxyLabel": _proxy_label(proxy),
        }

    session_info = _login_email_account_for_test(row, proxy=proxy)
    oauth_cache = _session_info_to_oauth_data(session_info, email=row["email"])
    if not oauth_cache.get("access_token"):
        raise ValueError("邮箱登录后未获取 accessToken")
    _persist_oauth_data(account_id, oauth_cache)
    return {
        "accessToken": str(oauth_cache["access_token"]),
        "chatgptAccountId": str(oauth_cache.get("chatgpt_account_id") or ""),
        "loginMs": int((time.time() - started) * 1000),
        "loginMode": "email_login",
        "proxy": proxy,
        "proxyLabel": _proxy_label(proxy),
    }


def _clear_pool_account_oauth_session(account_id: str) -> None:
    """清空已缓存的 ChatGPT token，强制走完整登录（等同重新导入后的登录流程）。"""
    _persist_oauth_data(account_id, {})


def _refresh_pool_account_credentials_from_material(account_id: str) -> bool:
    """用库内 material 行刷新邮箱密码/令牌（与重新粘贴导入一致）。"""
    row = get_pool_account(account_id)
    if not row:
        return False
    account_type = (row["account_type"] or "email").strip().lower()
    if account_type == "oauth":
        return False
    material = str(row["material"] or "").strip()
    if not material:
        return False
    try:
        account = parse_material_line(material.splitlines()[0] if "\n" in material else material)
    except ValueError:
        return False
    pool_email = str(row["email"] or "").strip().lower()
    if account.email.strip().lower() != pool_email:
        return False
    refreshed_material = "----".join(
        [account.email, account.password, account.client_id, account.refresh_token]
    )
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE pool_accounts
                SET password = ?, client_id = ?, refresh_token = ?, material = ?
                WHERE id = ?
                """,
                (account.password, account.client_id, account.refresh_token, refreshed_material, account_id),
            )
            conn.commit()
        finally:
            conn.close()
    return True


def rotate_account_proxy_from_pool(account_id: str) -> str:
    """从代理池取「下一个」代理并绑定（重新导入时也会分到新代理）。"""
    from core.app_settings import get_proxy_pool

    pool = [str(item).strip() for item in get_proxy_pool() if str(item).strip()]
    if not pool:
        return ""
    row = get_pool_account(account_id)
    if not row:
        return ""
    current = _account_proxy(row)
    if current in pool and len(pool) > 1:
        next_proxy = pool[(pool.index(current) + 1) % len(pool)]
    elif current in pool:
        next_proxy = current
    else:
        next_proxy = pool[hash(account_id) % len(pool)]
    if next_proxy != current:
        update_pool_account_proxy(account_id, next_proxy)
    return next_proxy


def _relogin_error_should_rotate_proxy(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("403", "401", "forbidden", "proxy", "timeout", "connection"))


def _prepare_account_for_relogin(
    account_id: str,
    *,
    proxy: str | None = None,
    rotate_proxy: bool = False,
) -> tuple[bool, bool]:
    """清 session、刷新素材、应用代理。返回 (素材已刷新, 代理已轮换)。"""
    _clear_pool_account_oauth_session(account_id)
    material_refreshed = _refresh_pool_account_credentials_from_material(account_id)
    proxy_rotated = False
    if rotate_proxy:
        rotate_account_proxy_from_pool(account_id)
        proxy_rotated = True
    elif proxy is not None:
        update_pool_account_proxy(account_id, str(proxy).strip())
    else:
        ensure_account_proxy_from_pool(account_id)
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE pool_accounts
                SET quota_data = '', quota_updated_at = NULL,
                    test_status = 'pending',
                    test_result = ?
                WHERE id = ?
                """,
                (json.dumps({"ok": False, "message": "重新登录中"}, ensure_ascii=False), account_id),
            )
            conn.commit()
        finally:
            conn.close()
    return material_refreshed, proxy_rotated


def ensure_account_proxy_from_pool(account_id: str) -> str:
    """账号未绑定代理时，从代理池按顺序分配一条。"""
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    current = _account_proxy(row)
    if current:
        return current
    from core.app_settings import get_proxy_pool

    pool = get_proxy_pool()
    if not pool:
        return ""
    assigned = pool[0]
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE pool_accounts SET assigned_proxy = ? WHERE id = ?",
                (assigned, account_id),
            )
            conn.commit()
        finally:
            conn.close()
    return assigned


def login_pool_account(
    account_id: str,
    *,
    force: bool = True,
    auto_follow_up: bool = False,
    model: str | None = None,
    message: str | None = None,
    proxy: str | None = None,
    rotate_proxy: bool = False,
) -> dict[str, Any]:
    """完整重新登录：清 token → 刷新素材 → 应用/轮换代理 → OTP 登录 → 校验额度；可选自动测试。"""
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    started = time.time()
    material_refreshed = False
    proxy_rotated = False
    proxy_assigned = ""
    if force:
        material_refreshed, proxy_rotated = _prepare_account_for_relogin(
            account_id,
            proxy=proxy,
            rotate_proxy=rotate_proxy,
        )
    else:
        if proxy is not None:
            update_pool_account_proxy(account_id, str(proxy).strip())
        else:
            proxy_assigned = ensure_account_proxy_from_pool(account_id)

    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    proxy = _account_proxy(row)
    from core.app_settings import get_proxy_pool

    if not proxy and get_proxy_pool():
        raise ValueError("请先在「设置」保存代理池，并在账号详情里选择代理后再登录")

    credentials: dict[str, Any] | None = None
    quota: dict[str, Any] | None = None
    verify_ms = 0
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            row = get_pool_account(account_id)
            if not row:
                raise ValueError("账号不存在")
            proxy = _account_proxy(row)
            credentials = _resolve_pool_account_credentials(row, force_login=True)
            verify_started = time.time()
            quota = query_chatgpt_quota(
                credentials["accessToken"],
                chatgpt_account_id=credentials["chatgptAccountId"],
                proxy=credentials.get("proxy", proxy),
            )
            verify_ms = int((time.time() - verify_started) * 1000)
            if not quota.get("ok", True):
                err = str(quota.get("error") or "额度接口返回失败").strip()
                raise ValueError(f"登录流程已完成，但额度校验未通过: {err}")
            update_account_quota(account_id, quota)
            last_exc = None
            break
        except Exception as exc:
            last_exc = exc
            _clear_pool_account_oauth_session(account_id)
            if attempt == 0 and _relogin_error_should_rotate_proxy(exc) and get_proxy_pool():
                rotate_account_proxy_from_pool(account_id)
                proxy_rotated = True
                continue
            _mark_account_abnormal(account_id, quota=quota if isinstance(quota, dict) else None, error=str(exc))
            raise last_exc from exc

    if not credentials or not quota:
        raise ValueError("重新登录失败")

    row = get_pool_account(account_id) or row
    proxy = _account_proxy(row)

    payload: dict[str, Any] = {
        "ok": True,
        "accountId": account_id,
        "email": row["email"],
        "accountType": (row["account_type"] or "email").strip().lower(),
        "loginMode": credentials.get("loginMode"),
        "loginMs": credentials.get("loginMs"),
        "proxy": proxy or credentials.get("proxy") or "",
        "proxyLabel": credentials.get("proxyLabel") or _proxy_label(proxy),
        "proxyAssigned": bool(proxy_assigned),
        "materialRefreshed": material_refreshed,
        "proxyRotated": proxy_rotated,
        "quotaSummary": quota.get("summary") or quota.get("planType") or "",
        "verifyMs": verify_ms,
        "quota": quota,
    }

    if auto_follow_up:
        test_payload = test_pool_account(account_id, model=model, message=message)
        payload["test"] = test_payload
        payload["testStatus"] = test_payload.get("testStatus")
        payload["testOk"] = str(test_payload.get("testStatus") or "").lower() == "success"

    log_activity(
        category="login",
        action="login.manual",
        message=f"{row['email']} 重新登录成功 ({credentials.get('loginMode')})",
        account_id=account_id,
        email=row["email"],
        status="success",
        duration_ms=int((time.time() - started) * 1000),
        detail=payload,
    )
    return payload


def query_pool_account_quota(account_id: str) -> dict[str, Any]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    credentials = _resolve_pool_account_credentials(row)
    quota = query_chatgpt_quota(
        credentials["accessToken"],
        chatgpt_account_id=credentials["chatgptAccountId"],
        proxy=credentials.get("proxy", _account_proxy(row)),
    )
    update_account_quota(account_id, quota)
    if not _quota_is_healthy(quota):
        _mark_account_abnormal(account_id, quota=quota)
    payload = {
        "accountId": account_id,
        "email": row["email"],
        "accountType": (row["account_type"] or "email").strip().lower(),
        "quota": quota,
        "loginMs": credentials.get("loginMs"),
        "loginMode": credentials.get("loginMode"),
    }
    log_activity(
        category="quota",
        action="quota.query",
        message=f"{row['email']} 额度: {quota.get('summary') or quota.get('planType') or '已查询'}",
        account_id=account_id,
        email=row["email"],
        status="success" if quota.get("ok", True) else "failed",
        duration_ms=credentials.get("loginMs"),
        detail=payload,
    )
    return payload


def read_pool_account_otp(account_id: str, *, max_age_seconds: int = 120) -> dict[str, Any]:
    from core.outlook_client import fetch_otp_with_account, otp_read_failure_reason

    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    email = (row["email"] or "").strip()
    account = outlook_account_from_row(row)
    try:
        otp = fetch_otp_with_account(
            account,
            after_ts=time.time() - max_age_seconds,
            max_wait=8,
            poll_interval=2,
            settle_seconds=0,
        )
    except Exception as exc:
        log_exception(
            category="otp",
            action="otp.read",
            message=f"{email} 读取验证码失败",
            exc=exc,
            account_id=account_id,
            email=email,
            detail={"maxAgeSeconds": max_age_seconds},
        )
        raise ValueError(otp_read_failure_reason(account, exc, max_age_seconds=max_age_seconds)) from exc

    log_activity(
        category="otp",
        action="otp.read",
        message=f"{email} 读取验证码成功",
        account_id=account_id,
        email=email,
        status="success",
        detail={"otpLength": len(str(otp)), "maxAgeSeconds": max_age_seconds},
    )
    return {
        "accountId": account_id,
        "email": email,
        "otp": otp,
    }


def get_pool_account(account_id: str) -> sqlite3.Row | None:
    with LOCK:
        conn = _connect()
        try:
            return conn.execute(
                """
                SELECT id, email, password, client_id, refresh_token, material,
                       account_type, oauth_data, status, test_status, test_result, last_test_at,
                       quota_data, quota_updated_at, assigned_proxy, mailbox_material, remark
                FROM pool_accounts WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
        finally:
            conn.close()


def update_pool_account_remark(account_id: str, remark: str | None) -> dict[str, Any]:
    account_id = str(account_id or "").strip()
    if not account_id:
        raise ValueError("缺少 accountId")
    text = str(remark or "").strip()
    with LOCK:
        conn = _connect()
        try:
            row = conn.execute("SELECT id, email FROM pool_accounts WHERE id = ?", (account_id,)).fetchone()
            if not row:
                raise ValueError("账号不存在")
            conn.execute("UPDATE pool_accounts SET remark = ? WHERE id = ?", (text, account_id))
            conn.commit()
        finally:
            conn.close()
    log_activity(
        category="admin",
        action="account.remark",
        message=f"更新账号备注: {row['email']}",
        status="success",
        detail={"accountId": account_id, "remark": text},
    )
    return {"ok": True, "accountId": account_id, "remark": text}


def set_pool_account_priority_sale(account_id: str, *, enabled: bool) -> dict[str, Any]:
    account_id = str(account_id or "").strip()
    if not account_id:
        raise ValueError("缺少 accountId")
    now = now_iso()
    with LOCK:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id, email, status FROM pool_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if not row:
                raise ValueError("账号不存在")
            if (row["status"] or "").strip().lower() == "assigned":
                raise ValueError("账号已分配，无法设置优先出售")
            if enabled:
                conn.execute(
                    "UPDATE pool_accounts SET priority_sale = 1, priority_sale_at = ? WHERE id = ?",
                    (now, account_id),
                )
                at = now
            else:
                conn.execute(
                    "UPDATE pool_accounts SET priority_sale = 0, priority_sale_at = NULL WHERE id = ?",
                    (account_id,),
                )
                at = None
            conn.commit()
            email = str(row["email"])
        finally:
            conn.close()
    log_activity(
        category="admin",
        action="account.priority_sale",
        message=f"{'开启' if enabled else '关闭'}优先出售: {email}",
        status="success",
        detail={"accountId": account_id, "enabled": enabled, "prioritySaleAt": at},
    )
    return {
        "ok": True,
        "accountId": account_id,
        "prioritySale": enabled,
        "prioritySaleAt": at,
    }


def update_account_test(account_id: str, *, status: str, result: dict[str, Any]) -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE pool_accounts
                SET test_status = ?, test_result = ?, last_test_at = ?
                WHERE id = ?
                """,
                (status, json.dumps(result, ensure_ascii=False), now_iso(), account_id),
            )
            conn.commit()
        finally:
            conn.close()


def oauth_data_dict(row: sqlite3.Row) -> dict[str, Any]:
    raw = row["oauth_data"] if "oauth_data" in row.keys() else ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def oauth_to_session_info(oauth: dict[str, Any]) -> dict[str, Any]:
    email = str(oauth.get("email") or "")
    user_id = str(oauth.get("chatgpt_user_id") or "")
    account_id = str(oauth.get("chatgpt_account_id") or "")
    info: dict[str, Any] = {
        "accessToken": oauth.get("access_token") or "",
        "user": {
            "email": email,
            "id": user_id,
        },
        "account": {
            "id": account_id,
            "planType": oauth.get("plan_type") or "",
        },
        "authProvider": "openai",
    }
    session_token = str(oauth.get("session_token") or "").strip()
    if session_token:
        info["sessionToken"] = session_token
    expires = str(oauth.get("expires") or oauth.get("expires_at") or "").strip()
    if expires:
        info["expires"] = expires
    refresh_token = str(oauth.get("refresh_token") or oauth.get("refreshToken") or "").strip()
    if refresh_token:
        info["refreshToken"] = refresh_token
        info["refresh_token"] = refresh_token
    id_token = str(oauth.get("id_token") or oauth.get("idToken") or "").strip()
    if id_token:
        info["idToken"] = id_token
        info["id_token"] = id_token
    return info


def _extract_chatgpt_refresh_token_from_material(material: str) -> str:
    raw = (material or "").strip()
    if not raw.startswith(("{", "[")):
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    items: list[dict[str, Any]] = []
    if isinstance(data, list):
        items = [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        accounts = data.get("accounts")
        if isinstance(accounts, list):
            items = [item for item in accounts if isinstance(item, dict)]
        elif isinstance(data.get("credentials"), dict) or data.get("type") == "oauth":
            items = [data]
    for item in items:
        credentials = item.get("credentials") if isinstance(item.get("credentials"), dict) else item
        refresh_token = str(
            credentials.get("refresh_token") or credentials.get("refreshToken") or ""
        ).strip()
        if refresh_token:
            return refresh_token
    return ""


def pool_account_to_session_info(row: sqlite3.Row) -> dict[str, Any]:
    oauth = oauth_data_dict(row)
    info = oauth_to_session_info(oauth)
    account_type = ((row["account_type"] if "account_type" in row.keys() else "") or "email").strip().lower()

    refresh_token = str(info.get("refreshToken") or info.get("refresh_token") or "").strip()
    if not refresh_token and account_type == "oauth":
        refresh_token = str(row["refresh_token"] or "").strip()
    if not refresh_token and account_type == "oauth":
        refresh_token = _extract_chatgpt_refresh_token_from_material(str(row["material"] or ""))
    if refresh_token:
        info["refreshToken"] = refresh_token
        info["refresh_token"] = refresh_token

    return info


def _parse_test_result(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": raw}
    return data if isinstance(data, dict) else None


def _get_cookie_value(browser_session, name: str) -> str | None:
    jar = getattr(browser_session.session, "cookies", None)
    if jar is None:
        return None
    for kwargs in (
        {"name": name, "domain": "chatgpt.com"},
        {"name": name, "domain": ".chatgpt.com"},
        {"name": name},
    ):
        try:
            value = jar.get(**kwargs)
            if value:
                return value
        except Exception:
            pass
    try:
        for cookie in jar:
            if getattr(cookie, "name", None) == name:
                return getattr(cookie, "value", None)
    except Exception:
        return None
    return None


def _login_email_account_for_test(row: sqlite3.Row, *, proxy: str = "") -> dict[str, Any]:
    from core.account_export import fetch_session
    from core.chatgpt_auth import get_csrf_token, get_providers, signin_openai
    from core.openai_auth import build_sentinel_header, follow_authorize, request_sentinel_token, validate_email_otp
    from core.outlook_client import OutlookAccount, fetch_otp_with_account
    from core.session import BrowserSession

    account = OutlookAccount(
        email=row["email"],
        password=row["password"],
        client_id=row["client_id"],
        refresh_token=row["refresh_token"],
    )
    session = BrowserSession(proxy if proxy else "")
    get_providers(session)
    csrf_token = get_csrf_token(session)
    authorize_url = signin_openai(session, csrf_token, account.email)
    otp_after_ts = time.time()
    follow_authorize(session, authorize_url)
    sentinel_resp = request_sentinel_token(session, "authorize_continue")
    sentinel_header, _ = build_sentinel_header(session, sentinel_resp, "authorize_continue")
    otp_code = fetch_otp_with_account(account, after_ts=otp_after_ts)
    validate_result = validate_email_otp(session, otp_code, sentinel_header)
    continue_url = validate_result.get("continue_url")
    if not continue_url:
        raise RuntimeError(f"验证码已提交，但响应缺少 continue_url: {validate_result}")
    headers = session.get_auth_navigate_headers(referer="https://auth.openai.com/email-verification")
    session.get(continue_url, headers=headers, allow_redirects=True)
    session_info = fetch_session(session)
    session_token = _get_cookie_value(session, "__Secure-next-auth.session-token")
    if session_token:
        session_info["sessionToken"] = session_token
    session_info.setdefault("authProvider", "openai")
    return session_info


def list_auto_test_account_ids() -> list[str]:
    with LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id FROM pool_accounts
                WHERE coalesce(test_status, '') != 'running'
                ORDER BY pool_type ASC, created_at ASC
                """
            ).fetchall()
            return [str(row["id"]) for row in rows]
        finally:
            conn.close()


def test_pool_account(
    account_id: str,
    *,
    model: str | None = None,
    message: str | None = None,
    source: str = "manual",
) -> dict[str, Any]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")

    account_type = (row["account_type"] or "email").strip().lower()
    last_event: dict[str, Any] | None = None
    for event in provision_pool_account_steps(account_id, model=model, message=message):
        if event.get("step") == "done":
            last_event = event
    if not last_event:
        raise ValueError("测试失败")

    detail = last_event.get("detail") or {}
    result = last_event.get("result") or {}
    status = str(last_event.get("testStatus") or detail.get("testStatus") or "failed")
    quota = result.get("quota") if isinstance(result.get("quota"), dict) else detail.get("quota")
    payload = {
        "accountId": account_id,
        "email": detail.get("email") or row["email"],
        "accountType": account_type,
        "testStatus": status,
        "result": result,
        "quota": quota if isinstance(quota, dict) else None,
    }
    log_activity(
        level="info" if status == "success" else "warn",
        category="test",
        action="test.auto" if source == "auto" else "test.manual",
        message=f"{payload['email']} {'自动' if source == 'auto' else '手动'}测试 {status}",
        account_id=account_id,
        email=payload["email"],
        status=status,
        detail=payload,
    )
    return payload


def export_pool_account(account_id: str, output_format: str) -> dict[str, Any]:
    import base64
    import zipfile
    from datetime import timezone
    from io import BytesIO

    from tools.session_json_converter import FORMATS, build_output_document, convert_session, sanitize_file_token

    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    oauth = oauth_data_dict(row)
    if not str(oauth.get("access_token") or "").strip():
        raise ValueError("账号尚未登录成功，无法导出")

    fmt = (output_format or "sub2api").strip().lower()
    if fmt not in (*FORMATS, "all"):
        raise ValueError("不支持的导出格式")

    email = row["email"]
    session_info = pool_account_to_session_info(row)
    now = datetime.now(timezone.utc)
    converted = convert_session(session_info, now=now, source_name=email, source_path="$")
    formats = FORMATS if fmt == "all" else (fmt,)

    if fmt == "all":
        buffer = BytesIO()
        used_names: dict[str, int] = {}
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for export_fmt in formats:
                if export_fmt == "sub2api":
                    document = build_output_document([converted], export_fmt, now)
                    archive.writestr("sub2api.json", json.dumps(document, ensure_ascii=False, indent=2) + "\n")
                    continue
                document = build_output_document([converted], export_fmt, now)
                base = sanitize_file_token(email)
                raw_name = f"{base}.{export_fmt}.json"
                count = used_names.get(raw_name, 0)
                used_names[raw_name] = count + 1
                name = raw_name
                if count:
                    stem, dot, suffix = raw_name.rpartition(".")
                    name = f"{stem}-{count + 1}{dot}{suffix}" if dot else f"{raw_name}-{count + 1}"
                archive.writestr(name, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{fmt}-export-{stamp}.zip"
        content = buffer.getvalue()
        mime_type = "application/zip"
    else:
        document = build_output_document([converted], fmt, now)
        if fmt == "sub2api":
            filename = "sub2api.json"
        else:
            filename = f"{sanitize_file_token(email)}.{fmt}.json"
        content = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        mime_type = "application/json"

    payload = {
        "accountId": account_id,
        "email": email,
        "filename": filename,
        "mimeType": mime_type,
        "contentBase64": base64.b64encode(content).decode("ascii"),
    }
    log_activity(
        category="export",
        action="export.account",
        message=f"{email} 导出 {fmt} -> {filename}",
        account_id=account_id,
        email=email,
        status="success",
        detail={
            "format": fmt,
            "filename": filename,
            "mimeType": mime_type,
            "bytes": len(content),
            "hasRefreshToken": bool(pool_account_to_session_info(row).get("refreshToken")),
        },
    )
    return payload


def account_has_chatgpt_refresh_token(row: sqlite3.Row) -> bool:
    oauth = oauth_data_dict(row)
    if str(oauth.get("refresh_token") or oauth.get("refreshToken") or "").strip():
        return True
    account_type = ((row["account_type"] if "account_type" in row.keys() else "") or "email").strip().lower()
    if account_type == "oauth":
        refresh_token = str(row["refresh_token"] if "refresh_token" in row.keys() else "").strip()
        if refresh_token:
            return True
    material = str(row["material"] if "material" in row.keys() else "")
    return bool(_extract_chatgpt_refresh_token_from_material(material))


def link_optional_oauth_pool_account(
    account_id: str,
    *,
    oauth_method: str = "manual",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
    material: str = "",
) -> dict[str, Any]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    if account_has_chatgpt_refresh_token(row):
        raise ValueError("该账号已有 OAuth refresh_token")

    records, _parse_skipped, _account_type = _parse_import_records(
        material,
        "oauth",
        oauth_method=oauth_method,
        session_id=session_id,
        auth_input=auth_input,
        state=state,
    )
    if not records:
        raise ValueError("未能解析 OAuth 授权信息")
    if len(records) > 1:
        raise ValueError("一次只能为一个账号绑定 OAuth")

    record = records[0]
    raw_oauth = record.get("oauth_data") or ""
    try:
        new_oauth = json.loads(raw_oauth) if raw_oauth else {}
    except json.JSONDecodeError as exc:
        raise ValueError(f"OAuth 数据解析失败: {exc}") from exc
    if not isinstance(new_oauth, dict):
        raise ValueError("OAuth 授权结果无效")
    if not str(new_oauth.get("refresh_token") or "").strip():
        raise ValueError("OAuth 授权结果缺少 refresh_token")

    merged = oauth_data_dict(row)
    for key in (
        "refresh_token",
        "access_token",
        "id_token",
        "chatgpt_account_id",
        "chatgpt_user_id",
        "plan_type",
        "expires_at",
        "expires",
        "client_id",
        "organization_id",
    ):
        value = str(new_oauth.get(key) or "").strip()
        if value:
            merged[key] = value
    merged["email"] = str(merged.get("email") or row["email"] or new_oauth.get("email") or "").strip()
    merged["oauth_linked_at"] = now_iso()
    merged["oauth_link_mode"] = "optional"
    _persist_oauth_data(account_id, merged)

    log_activity(
        category="oauth",
        action="oauth.link_optional",
        message=f"{row['email']} 已可选绑定 OAuth（含 refresh_token）",
        account_id=account_id,
        email=row["email"],
        status="success",
        detail={
            "accountType": row["account_type"] or "email",
            "hasRefreshToken": True,
            "oauthMethod": oauth_method,
        },
    )
    return {
        "ok": True,
        "accountId": account_id,
        "email": row["email"],
        "accountType": row["account_type"] or "email",
        "hasRefreshToken": True,
    }


def reauthorize_pool_account(
    account_id: str,
    *,
    oauth_method: str = "manual",
    session_id: str = "",
    auth_input: str = "",
    state: str = "",
    material: str = "",
) -> dict[str, Any]:
    row = get_pool_account(account_id)
    if not row:
        raise ValueError("账号不存在")
    if (row["status"] or "").strip().lower() == "assigned":
        raise ValueError("账号已分配给卡密，暂不支持重新授权")

    records, _parse_skipped, _account_type = _parse_import_records(
        material,
        "oauth",
        oauth_method=oauth_method,
        session_id=session_id,
        auth_input=auth_input,
        state=state,
    )
    if not records:
        raise ValueError("未能解析 OAuth 授权信息")
    if len(records) > 1:
        raise ValueError("重新授权一次只能处理一个账号")

    record = records[0]
    group_name = normalize_group_name("oauth", account_type="oauth")
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE pool_accounts
                SET account_type = 'oauth',
                    material = ?,
                    client_id = ?,
                    refresh_token = ?,
                    oauth_data = ?,
                    group_name = ?,
                    test_status = 'pending',
                    test_result = ?,
                    last_test_at = NULL,
                    quota_data = '',
                    quota_updated_at = NULL
                WHERE id = ?
                """,
                (
                    record.get("material") or "",
                    record.get("client_id") or "",
                    record.get("refresh_token") or "",
                    record.get("oauth_data") or "",
                    group_name,
                    json.dumps({}, ensure_ascii=False),
                    account_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    enqueue_provision_accounts([account_id])
    log_activity(
        category="oauth",
        action="oauth.reauthorize",
        message=f"{row['email']} 已提交重新授权",
        account_id=account_id,
        email=row["email"],
        status="running",
        detail={
            "oauthMethod": oauth_method,
            "clientId": record.get("client_id") or "",
        },
    )
    return {
        "ok": True,
        "accountId": account_id,
        "email": row["email"],
        "accountType": "oauth",
        "queued": 1,
    }


def delete_pool_account(account_id: str) -> None:
    row = get_pool_account(account_id)
    email = row["email"] if row else account_id
    with LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT id, status FROM pool_accounts WHERE id = ?",
                (account_id,),
            ).fetchone()
            if not row:
                raise ValueError("账号不存在")
            if row["status"] == "assigned":
                raise ValueError("账号已分配给卡密，请先删除对应卡密")
            conn.execute("DELETE FROM pool_accounts WHERE id = ?", (account_id,))
            conn.commit()
        except Exception:
            _safe_rollback(conn)
            raise
        finally:
            conn.close()
    log_activity(
        category="delete",
        action="account.delete",
        message=f"删除账号 {email}",
        account_id=account_id,
        email=email,
        status="success",
    )


def create_card_keys(count: int, *, pool_type: str = "pp") -> list[str]:
    if count < 1:
        raise ValueError("至少生成 1 个卡密")
    if count > 500:
        raise ValueError("单次最多生成 500 个卡密")

    normalized_pool = normalize_pool_type(pool_type)
    created: list[str] = []
    now = now_iso()
    with LOCK:
        conn = _connect()
        try:
            for _ in range(count):
                code = generate_card_code(conn, normalized_pool)
                row_id = secrets.token_urlsafe(8)
                conn.execute(
                    """
                    INSERT INTO card_keys (id, code, status, pool_type, created_at)
                    VALUES (?, ?, 'available', ?, ?)
                    """,
                    (row_id, code, normalized_pool, now),
                )
                created.append(code)
            conn.commit()
        finally:
            conn.close()
    log_activity(
        category="card",
        action="card.create",
        message=f"生成 {len(created)} 个{pool_type_label(normalized_pool)}卡密",
        status="success",
        detail={"count": len(created), "poolType": normalized_pool, "codesPreview": created[:5]},
    )
    return created


def redeem_card(code: str) -> dict[str, Any]:
    normalized, expected_pool = parse_card_code(code)
    now = now_iso()
    try:
        with LOCK:
            conn = _connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                card = conn.execute(
                    "SELECT id, code, status, account_id, pool_type FROM card_keys WHERE code = ?",
                    (normalized,),
                ).fetchone()
                if not card:
                    raise ValueError("卡密不存在")
                card_pool = normalize_pool_type(card["pool_type"] if "pool_type" in card.keys() else expected_pool)
                if card_pool != expected_pool:
                    raise ValueError(f"卡密类型不匹配：该卡密属于 {pool_type_label(card_pool)} 池")
                if card["status"] != "available":
                    if card["account_id"]:
                        account = conn.execute(
                            """
                            SELECT id, email, password, client_id, refresh_token, material,
                                   account_type, oauth_data
                            FROM pool_accounts WHERE id = ?
                            """,
                            (card["account_id"],),
                        ).fetchone()
                        if account:
                            _safe_rollback(conn)
                            payload = _account_payload(account, card["code"], reused=True)
                            log_activity(
                                category="redeem",
                                action="redeem.reuse",
                                message=f"卡密 {normalized} 重复取号 -> {account['email']}",
                                account_id=account["id"],
                                email=account["email"],
                                card_code=normalized,
                                status="success",
                                detail={"reused": True},
                            )
                            return payload
                    raise ValueError("卡密已被使用")

                account = conn.execute(
                    """
                    SELECT id, email, password, client_id, refresh_token, material,
                           account_type, oauth_data
                    FROM pool_accounts
                    WHERE status = 'available' AND test_status = 'success' AND pool_type = ?
                    ORDER BY priority_sale DESC,
                             CASE WHEN coalesce(priority_sale, 0) = 1 THEN priority_sale_at ELSE NULL END ASC,
                             created_at ASC
                    LIMIT 1
                    """,
                    (card_pool,),
                ).fetchone()
                if not account:
                    raise ValueError(f"暂无 {pool_type_label(card_pool)} 测试通过的可用账号，请稍后再试或联系管理员")

                conn.execute(
                    """
                    UPDATE card_keys
                    SET status = 'used', account_id = ?, used_at = ?
                    WHERE id = ?
                    """,
                    (account["id"], now, card["id"]),
                )
                conn.execute(
                    """
                    UPDATE pool_accounts
                    SET status = 'assigned', card_code = ?, assigned_at = ?
                    WHERE id = ?
                    """,
                    (normalized, now, account["id"]),
                )
                conn.commit()
                payload = _account_payload(account, normalized, reused=False)
            except Exception:
                _safe_rollback(conn)
                raise
            finally:
                conn.close()
    except ValueError as exc:
        log_activity(
            level="warn",
            category="redeem",
            action="redeem.failed",
            message=str(exc),
            card_code=normalized,
            status="failed",
            detail={"code": normalized},
        )
        raise

    log_activity(
        category="redeem",
        action="redeem.success",
        message=f"卡密 {normalized} 分配 -> {payload['email']}",
        account_id=payload["id"],
        email=payload["email"],
        card_code=normalized,
        status="success",
        detail={
            "reused": False,
            "accountType": payload.get("accountType"),
            "hasSession": bool(payload.get("sessionInfo")),
        },
    )
    return payload


def _account_payload(row: sqlite3.Row, card_code: str, *, reused: bool) -> dict[str, Any]:
    account_type = (row["account_type"] if "account_type" in row.keys() else "email") or "email"
    oauth = oauth_data_dict(row)
    payload: dict[str, Any] = {
        "id": row["id"],
        "email": row["email"],
        "password": row["password"],
        "clientId": row["client_id"],
        "refreshToken": row["refresh_token"],
        "material": row["material"],
        "accountType": account_type,
        "cardCode": card_code,
        "reused": reused,
    }
    if str(oauth.get("access_token") or "").strip():
        payload["oauthData"] = oauth
        payload["sessionInfo"] = pool_account_to_session_info(row)
    return payload


def get_stats(*, pool_type: str | None = None) -> dict[str, Any]:
    normalized_pool = normalize_pool_type(pool_type) if pool_type else None
    with LOCK:
        conn = _connect()
        try:
            def pool_stats(pool: str) -> dict[str, int]:
                account_rows = conn.execute(
                    """
                    SELECT status, test_status, quota_data
                    FROM pool_accounts
                    WHERE pool_type = ?
                    """,
                    (pool,),
                ).fetchall()
                available = 0
                failed = 0
                for account_row in account_rows:
                    pool_status = str(account_row["status"] or "").strip().lower()
                    if _account_counts_as_failed(account_row["test_status"], account_row["quota_data"]):
                        failed += 1
                    elif pool_status == "available" and str(account_row["test_status"] or "").strip().lower() == "success":
                        available += 1
                card_row = conn.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available,
                        SUM(CASE WHEN status = 'used' THEN 1 ELSE 0 END) AS used
                    FROM card_keys
                    WHERE pool_type = ?
                    """,
                    (pool,),
                ).fetchone()
                return {
                    "accountsAvailable": available,
                    "accountsFailed": failed,
                    "cardsAvailable": int(card_row["available"] or 0) if card_row else 0,
                    "cardsUsed": int(card_row["used"] or 0) if card_row else 0,
                }

            if normalized_pool:
                single = pool_stats(normalized_pool)
                return {
                    "accountsTotal": single["accountsAvailable"] + single["accountsFailed"],
                    "accountsAvailable": single["accountsAvailable"],
                    "accountsAssigned": int(
                        conn.execute(
                            "SELECT COUNT(*) FROM pool_accounts WHERE pool_type = ? AND status = 'assigned'",
                            (normalized_pool,),
                        ).fetchone()[0]
                    ),
                    "cardsTotal": single["cardsAvailable"] + single["cardsUsed"],
                    "cardsAvailable": single["cardsAvailable"],
                    "cardsUsed": single["cardsUsed"],
                    "accountsFailed": single["accountsFailed"],
                    "poolType": normalized_pool,
                }

            pp = pool_stats("pp")
            go = pool_stats("go")
            return {
                "overview": True,
                "pp": pp,
                "go": go,
                "poolType": "",
            }
        finally:
            conn.close()


def list_cards_page(page: int = 1, page_size: int = 10, *, pool_type: str | None = None) -> dict[str, Any]:
    page = normalize_page(page)
    page_size = normalize_page_size(page_size)
    normalized_pool = normalize_pool_type(pool_type) if pool_type else None
    with LOCK:
        conn = _connect()
        try:
            where_sql = ""
            params: list[Any] = []
            if normalized_pool:
                where_sql = "WHERE c.pool_type = ?"
                params.append(normalized_pool)
            total = int(conn.execute(f"SELECT COUNT(*) FROM card_keys c {where_sql}", params).fetchone()[0])
            meta = _paginate(total, page, page_size)
            rows = conn.execute(
                f"""
                SELECT c.code, c.status, c.pool_type, c.created_at, c.used_at, a.email AS account_email
                FROM card_keys c
                LEFT JOIN pool_accounts a ON a.id = c.account_id
                {where_sql}
                ORDER BY c.created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, meta["pageSize"], meta["offset"]),
            ).fetchall()
            return {
                **meta,
                "poolType": normalized_pool or "all",
                "items": [
                    {
                        "code": row["code"],
                        "status": row["status"],
                        "poolType": normalize_pool_type(row["pool_type"] if "pool_type" in row.keys() else "pp"),
                        "createdAt": row["created_at"],
                        "usedAt": row["used_at"],
                        "accountEmail": row["account_email"],
                    }
                    for row in rows
                ],
            }
        finally:
            conn.close()


def list_accounts_page(
    page: int = 1,
    page_size: int = 10,
    *,
    group: str | None = None,
    pool_type: str | None = None,
) -> dict[str, Any]:
    page = normalize_page(page)
    page_size = normalize_page_size(page_size)
    group_filter = ""
    normalized_pool = normalize_pool_type(pool_type) if pool_type else None
    if (group or "").strip() and str(group).strip().lower() not in {"all", ""}:
        group_filter = normalize_group_name(group)
    with LOCK:
        conn = _connect()
        try:
            where_parts: list[str] = []
            params: list[Any] = []
            if normalized_pool:
                where_parts.append("pool_type = ?")
                params.append(normalized_pool)
            if group_filter:
                where_parts.append("group_name = ?")
                params.append(group_filter)
            where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
            total = int(conn.execute(f"SELECT COUNT(*) FROM pool_accounts {where_sql}", params).fetchone()[0])
            meta = _paginate(total, page, page_size)
            rows = conn.execute(
                f"""
                SELECT id, email, status, card_code, created_at, assigned_at,
                       account_type, group_name, oauth_data, test_status, test_result, last_test_at,
                       quota_data, quota_updated_at, assigned_proxy, mailbox_material,
                       client_id, refresh_token, material, pool_type, remark,
                       priority_sale, priority_sale_at
                FROM pool_accounts
                {where_sql}
                ORDER BY group_name ASC, created_at DESC
                LIMIT ? OFFSET ?
                """,
                (*params, meta["pageSize"], meta["offset"]),
            ).fetchall()
            items = []
            for row in rows:
                quota = _parse_quota_data(row["quota_data"])
                oauth = oauth_data_dict(row)
                items.append(
                    {
                        "id": row["id"],
                        "email": row["email"],
                        "accountType": row["account_type"] or "email",
                        "poolType": normalize_pool_type(row["pool_type"] if "pool_type" in row.keys() else normalized_pool or "pp"),
                        "groupName": row["group_name"] or normalize_group_name(None, account_type=row["account_type"] or "email"),
                        "status": row["status"],
                        "cardCode": row["card_code"],
                        "createdAt": row["created_at"],
                        "assignedAt": row["assigned_at"],
                        "testStatus": row["test_status"],
                        "testResult": _parse_test_result(row["test_result"]),
                        "lastTestAt": row["last_test_at"],
                        "quota": quota,
                        "quotaUpdatedAt": row["quota_updated_at"],
                        "planType": str((quota or {}).get("planType") or oauth.get("plan_type") or "").strip(),
                        "assignedProxy": _account_proxy(row),
                        "proxyLabel": _proxy_label(_account_proxy(row)),
                        "hasRefreshToken": account_has_chatgpt_refresh_token(row),
                        "hasMailbox": account_has_mailbox(row),
                        "remark": str(row["remark"] or "").strip() if "remark" in row.keys() else "",
                        "prioritySale": bool(row["priority_sale"]) if "priority_sale" in row.keys() else False,
                        "prioritySaleAt": row["priority_sale_at"] if "priority_sale_at" in row.keys() else None,
                    }
                )
            return {
                **meta,
                "group": group_filter or "all",
                "poolType": normalized_pool or "all",
                "items": items,
            }
        finally:
            conn.close()


def delete_card_key(code: str) -> None:
    normalized = normalize_card_code(code)
    with LOCK:
        conn = _connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            card = conn.execute(
                "SELECT id, account_id FROM card_keys WHERE code = ?",
                (normalized,),
            ).fetchone()
            if not card:
                raise ValueError("卡密不存在")

            if card["account_id"]:
                conn.execute(
                    """
                    UPDATE pool_accounts
                    SET status = 'available', card_code = NULL, assigned_at = NULL
                    WHERE id = ?
                    """,
                    (card["account_id"],),
                )

            conn.execute("DELETE FROM card_keys WHERE id = ?", (card["id"],))
            conn.commit()
        except Exception:
            _safe_rollback(conn)
            raise
        finally:
            conn.close()
    log_activity(
        category="delete",
        action="card.delete",
        message=f"删除卡密 {normalized}",
        card_code=normalized,
        status="success",
        detail={"releasedAccountId": card["account_id"] if card else ""},
    )
