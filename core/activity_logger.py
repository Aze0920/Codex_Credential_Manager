# -*- coding: utf-8 -*-
"""结构化运行日志：持久化到 SQLite，供后台超级详细审计。"""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.db_config import get_database_path

DB_PATH = get_database_path()
LOCK = threading.RLock()

SENSITIVE_KEYS = {
    "password",
    "refresh_token",
    "refreshtoken",
    "access_token",
    "accesstoken",
    "id_token",
    "idtoken",
    "session_token",
    "sessiontoken",
    "contentbase64",
    "authorization",
    "cookie",
    "client_secret",
    "clientsecret",
    "token",
    "secret",
    "otp",
    "code",
}

LEVELS = ("debug", "info", "warn", "error")
CATEGORIES = (
    "system",
    "admin",
    "settings",
    "import",
    "provision",
    "login",
    "quota",
    "test",
    "export",
    "redeem",
    "card",
    "oauth",
    "otp",
    "delete",
    "client",
)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_page(value: Any) -> int:
    try:
        page = int(value)
    except (TypeError, ValueError):
        page = 1
    return max(1, page)


def _normalize_page_size(value: Any) -> int:
    try:
        size = int(value)
    except (TypeError, ValueError):
        size = 100
    return max(1, min(size, 500))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _new_log_id() -> str:
    return secrets.token_hex(8)


def _normalize_key(key: str) -> str:
    return key.replace("-", "_").lower()


def _truncate_text(value: str, limit: int = 240) -> str:
    text = value.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…(+{len(text) - limit} chars)"


def _sanitize_value(key: str, value: Any, *, depth: int = 0) -> Any:
    if depth > 8:
        return "[max-depth]"
    normalized = _normalize_key(key)
    if normalized in SENSITIVE_KEYS:
        if value in (None, "", [], {}):
            return value
        if isinstance(value, str):
            if len(value) <= 12:
                return "***"
            return f"{value[:6]}…{value[-4:]} (len={len(value)})"
        return "[redacted]"
    if isinstance(value, dict):
        return {k: _sanitize_value(str(k), v, depth=depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > 50:
            head = [_sanitize_value(key, item, depth=depth + 1) for item in value[:50]]
            head.append(f"…(+{len(value) - 50} items)")
            return head
        return [_sanitize_value(key, item, depth=depth + 1) for item in value]
    if isinstance(value, str) and len(value) > 2000:
        return _truncate_text(value, 2000)
    return value


def sanitize_detail(detail: Any) -> Any:
    if detail is None:
        return {}
    if isinstance(detail, dict):
        return _sanitize_value("detail", detail)
    if isinstance(detail, BaseException):
        return {
            "exceptionType": type(detail).__name__,
            "exceptionMessage": str(detail),
            "traceback": traceback.format_exc(),
        }
    return _sanitize_value("detail", detail)


def ensure_activity_logs_table() -> None:
    with LOCK:
        conn = _connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL DEFAULT 'info',
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    message TEXT NOT NULL,
                    account_id TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    card_code TEXT NOT NULL DEFAULT '',
                    client_id TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    duration_ms INTEGER,
                    detail_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_activity_logs_created
                    ON activity_logs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_activity_logs_category
                    ON activity_logs(category, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_activity_logs_email
                    ON activity_logs(email, created_at DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()


def log_activity(
    *,
    level: str = "info",
    category: str,
    action: str,
    message: str,
    account_id: str = "",
    email: str = "",
    card_code: str = "",
    client_id: str = "",
    status: str = "",
    duration_ms: int | None = None,
    detail: Any = None,
    error: str = "",
) -> str:
    ensure_activity_logs_table()
    log_id = _new_log_id()
    normalized_level = level if level in LEVELS else "info"
    normalized_category = category if category in CATEGORIES else "system"
    payload = sanitize_detail(detail if detail is not None else {})
    if error:
        if not isinstance(payload, dict):
            payload = {"data": payload}
        payload["error"] = error
    with LOCK:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO activity_logs (
                    id, created_at, level, category, action, message,
                    account_id, email, card_code, client_id, status,
                    duration_ms, detail_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    _now_iso(),
                    normalized_level,
                    normalized_category,
                    action,
                    message,
                    (account_id or "").strip(),
                    (email or "").strip(),
                    (card_code or "").strip(),
                    (client_id or "").strip(),
                    (status or "").strip(),
                    duration_ms,
                    json.dumps(payload, ensure_ascii=False, default=str),
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return log_id


def log_exception(
    *,
    category: str,
    action: str,
    message: str,
    exc: BaseException,
    **fields: Any,
) -> str:
    detail = fields.pop("detail", None)
    merged = sanitize_detail(detail or {})
    if not isinstance(merged, dict):
        merged = {"data": merged}
    merged.update(
        {
            "exceptionType": type(exc).__name__,
            "exceptionMessage": str(exc),
            "traceback": traceback.format_exc(),
        }
    )
    return log_activity(
        level="error",
        category=category,
        action=action,
        message=message,
        status="failed",
        detail=merged,
        error=str(exc),
        **fields,
    )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    detail: Any = {}
    raw = row["detail_json"] or "{}"
    try:
        detail = json.loads(raw)
    except json.JSONDecodeError:
        detail = {"raw": raw}
    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "level": row["level"],
        "category": row["category"],
        "action": row["action"],
        "message": row["message"],
        "accountId": row["account_id"] or "",
        "email": row["email"] or "",
        "cardCode": row["card_code"] or "",
        "clientId": row["client_id"] or "",
        "status": row["status"] or "",
        "durationMs": row["duration_ms"],
        "detail": detail,
    }


def list_activity_logs(
    *,
    page: int = 1,
    page_size: int = 100,
    category: str | None = None,
    level: str | None = None,
    email: str | None = None,
    action: str | None = None,
) -> dict[str, Any]:
    ensure_activity_logs_table()
    page = _normalize_page(page)
    page_size = _normalize_page_size(page_size)
    offset = (page - 1) * page_size

    where: list[str] = []
    params: list[Any] = []
    if category and category in CATEGORIES:
        where.append("category = ?")
        params.append(category)
    if level and level in LEVELS:
        where.append("level = ?")
        params.append(level)
    if email:
        where.append("email LIKE ?")
        params.append(f"%{email.strip()}%")
    if action:
        where.append("action LIKE ?")
        params.append(f"%{action.strip()}%")

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with LOCK:
        conn = _connect()
        try:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM activity_logs {clause}",
                params,
            ).fetchone()
            total = int(total_row["c"]) if total_row else 0
            rows = conn.execute(
                f"""
                SELECT id, created_at, level, category, action, message,
                       account_id, email, card_code, client_id, status,
                       duration_ms, detail_json
                FROM activity_logs
                {clause}
                ORDER BY created_at DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, page_size, offset),
            ).fetchall()
        finally:
            conn.close()

    items = [_row_to_dict(row) for row in rows]
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "total": total,
        "totalPages": max(1, (total + page_size - 1) // page_size),
        "filters": {
            "category": category or "",
            "level": level or "",
            "email": email or "",
            "action": action or "",
        },
    }


def clear_all_activity_logs() -> int:
    ensure_activity_logs_table()
    with LOCK:
        conn = _connect()
        try:
            total_row = conn.execute("SELECT COUNT(*) AS c FROM activity_logs").fetchone()
            deleted = int(total_row["c"]) if total_row else 0
            conn.execute("DELETE FROM activity_logs")
            conn.commit()
        finally:
            conn.close()
    log_activity(
        category="admin",
        action="logs.clear",
        message=f"已清空 {deleted} 条运行日志",
        status="success",
        detail={"deleted": deleted},
    )
    return deleted
