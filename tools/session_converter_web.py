#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch web UI for:
  Outlook material -> ChatGPT OTP login -> /api/auth/session -> JSON exports.

Run:
  python3 tools/session_converter_web.py
Open:
  http://127.0.0.1:8765
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, request, send_file, stream_with_context


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.account_export import fetch_session
from core.chatgpt_auth import get_csrf_token, get_providers, signin_openai
from core.openai_auth import (
    build_sentinel_header,
    follow_authorize,
    request_sentinel_token,
    validate_email_otp,
)
from core.outlook_client import OutlookAccount, fetch_otp_with_account, otp_read_failure_reason
from core.session import BrowserSession
from core.card_store import (
    is_valid_card_code,
    DB_PATH,
    create_card_keys,
    delete_card_key,
    delete_pool_account,
    export_pool_account,
    get_stats,
    import_pool_accounts,
    import_pool_accounts_background,
    iter_import_pool_accounts,
    init_db,
    list_accounts_page,
    list_cards_page,
    query_pool_account_quota,
    read_pool_account_otp,
    redeem_card,
    link_mailbox_to_oauth_account,
    link_optional_oauth_pool_account,
    reauthorize_pool_account,
    update_pool_account_proxy,
    update_pool_account_remark,
    set_pool_account_priority_sale,
    test_pool_account,
)
from core.openai_oauth import generate_auth_url
from core.account_tester import DEFAULT_TEST_MESSAGE, DEFAULT_TEST_MODEL, TEST_MODELS
from core.app_settings import (
    apply_runtime_settings,
    verify_admin_password,
    get_public_settings,
    get_test_settings,
    update_settings,
)
from core.auto_test_scheduler import request_auto_test_now, start_auto_test_scheduler
from core.api_errors import get_request_lang, public_error_message
from core.api_gateway import (
    extract_bearer_token,
    forward_gateway_request,
    get_public_api_gateway_settings,
    reset_api_gateway_key,
    resolve_public_base_url,
    verify_api_gateway_key,
)
from core.activity_logger import clear_all_activity_logs, log_activity, log_exception, list_activity_logs
from core.app_version import align_runtime_version, build_version_payload, get_app_version, get_host_install_dir
from core.update_job import get_update_status, start_update_job
from core.db_config import create_database_backup, get_database_path, list_database_backups
from core.proxy_tester import test_proxy_pool
from tools.admin_panel_html import ADMIN_HTML
from tools.session_json_converter import (
    FORMATS,
    build_output_document,
    convert_session,
    sanitize_file_token,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

app = Flask(__name__)
DEFAULT_CONCURRENCY = 3
MAX_CONCURRENCY = 10
COMPLETED_CACHE_TTL_SECONDS = 120
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")  # 启动默认值，运行时以 app_settings 为准
ADMIN_TOKEN_TTL_SECONDS = 12 * 60 * 60
ADMIN_TOKENS: dict[str, float] = {}
ADMIN_BUILD_ID = int(Path(__file__).stat().st_mtime)
APP_VERSION = align_runtime_version()
SERVER_FEATURES = ("delete", "import-login", "sse-text-v2", "sqlite-settings", "account-groups", "import-stream", "import-background", "api-gateway")
ACCOUNT_STATUSES = {
    "idle": "待处理",
    "running": "登录中",
    "success": "成功",
    "error": "失败",
}


@dataclass
class AccountRow:
    id: str
    email: str
    password: str
    client_id: str
    refresh_token: str
    material: str
    status: str = "idle"
    selected: bool = True
    error: str = ""
    otp: str = ""
    exported_formats: list[str] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    session_info: dict[str, Any] | None = None
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    running_job_id: str | None = None


@dataclass
class Job:
    id: str
    client_id: str
    row_id: str
    email: str
    format: str
    status: str = "queued"
    logs: list[str] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


CLIENTS: dict[str, dict[str, dict[str, Any]]] = {}
LOCK = threading.RLock()


def issue_admin_token() -> str:
    token = secrets.token_urlsafe(32)
    ADMIN_TOKENS[token] = time.time() + ADMIN_TOKEN_TTL_SECONDS
    return token


def require_admin_token() -> str | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:].strip()
    expires_at = ADMIN_TOKENS.get(token)
    if not expires_at or expires_at < time.time():
        ADMIN_TOKENS.pop(token, None)
        return None
    return token


def admin_required():
    if not require_admin_token():
        return jsonify({"error": "未授权或登录已过期"}), 401
    return None


def pool_account_records(material: str) -> list[dict[str, str]]:
    records, _ = parse_account_import(material, "email")
    return records


def parse_account_import(material: str, account_type: str):
    from core.account_parser import parse_account_import as _parse

    return _parse(material, account_type)


def upsert_redeemed_row(client_id: str, account: dict[str, Any]) -> AccountRow:
    rows_store = rows_for_client(client_id)
    row_id = str(account["id"])
    row = rows_store.get(row_id)
    session_info = account.get("sessionInfo")
    has_session = isinstance(session_info, dict) and bool(
        str(session_info.get("accessToken") or session_info.get("access_token") or "").strip()
    )
    if row is None:
        row = AccountRow(
            id=row_id,
            email=account["email"],
            password=account.get("password") or "",
            client_id=account.get("clientId") or "",
            refresh_token=account.get("refreshToken") or "",
            material=account["material"],
            session_info=session_info if has_session else None,
            status="success" if has_session else "idle",
            selected=True,
        )
        rows_store[row_id] = row
    else:
        row.email = account["email"]
        row.password = account.get("password") or ""
        row.client_id = account.get("clientId") or ""
        row.refresh_token = account.get("refreshToken") or ""
        row.material = account["material"]
        row.selected = True
        if has_session:
            row.session_info = session_info
            row.status = "success"
        elif not row.session_info:
            row.status = "idle"
    row.error = ""
    row.updated_at = now_iso()
    return row


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_output_format(value: str | None) -> str:
    return (value or "sub2api").strip().lower()


def get_request_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def api_error_response(exc: BaseException, status: int = 400):
    lang = get_request_lang()
    fallback = "Operation failed. Please try again." if lang == "en" else "操作失败，请稍后重试"
    return jsonify({"error": public_error_message(exc, lang=lang, fallback=fallback)}), status


def _register_api_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def api_not_found(error):  # noqa: ARG001
        if request.path.startswith("/api/"):
            return jsonify({"error": f"接口不存在: {request.path}，请重启服务后重试"}), 404
        return error

    @app.errorhandler(405)
    def api_method_not_allowed(error):  # noqa: ARG001
        if request.path.startswith("/api/"):
            return jsonify({"error": f"请求方法不允许: {request.method} {request.path}"}), 405
        return error


def _register_gateway_routes(app: Flask) -> None:
    gateway_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    gateway_prefixes = (
        "/v1",
        "/codex/v1",
        "/openrouter/v1",
        "/groq/v1",
        "/deepseek/v1",
        "/moonshot/v1",
        "/siliconflow/v1",
        "/cloudflare/v1",
    )

    def _handle_gateway(_subpath: str = ""):
        if request.method == "OPTIONS":
            return Response("", status=204)
        token = extract_bearer_token(request.headers.get("Authorization"))
        if not verify_api_gateway_key(token):
            return jsonify({"error": {"message": "API 密钥无效", "type": "invalid_api_key"}}), 401
        try:
            status, headers, content = forward_gateway_request(
                method=request.method,
                path=request.path,
                query_string=request.query_string,
                headers={key: value for key, value in request.headers.items()},
                body=request.get_data(),
            )
        except Exception as exc:
            log_exception(
                category="api",
                action="gateway.forward",
                message="API 网关转发失败",
                exc=exc,
                detail={"path": request.path, "method": request.method},
            )
            return api_error_response(exc)
        return Response(content, status=status, headers=headers)

    for prefix in gateway_prefixes:
        endpoint_root = "gateway_root_" + prefix.strip("/").replace("/", "_")
        endpoint_path = "gateway_path_" + prefix.strip("/").replace("/", "_")
        app.add_url_rule(prefix, endpoint=endpoint_root, view_func=_handle_gateway, methods=gateway_methods)
        app.add_url_rule(
            f"{prefix}/<path:subpath>",
            endpoint=endpoint_path,
            view_func=_handle_gateway,
            methods=gateway_methods,
        )


def get_client_id(payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    client_id = str(request.headers.get("X-Client-Id") or payload.get("client_id") or "").strip()
    if not re.match(r"^[A-Za-z0-9_-]{24,128}$", client_id):
        raise ValueError("缺少或非法 client id")
    return client_id


def client_store(client_id: str) -> dict[str, dict[str, Any]]:
    return CLIENTS.setdefault(client_id, {"rows": {}, "jobs": {}})


def rows_for_client(client_id: str) -> dict[str, AccountRow]:
    return client_store(client_id)["rows"]  # type: ignore[return-value]


def jobs_for_client(client_id: str) -> dict[str, Job]:
    return client_store(client_id)["jobs"]  # type: ignore[return-value]


def account_row_from_public(item: dict[str, Any]) -> AccountRow | None:
    email = str(item.get("email") or "").strip()
    password = str(item.get("password") or "")
    client_id = str(item.get("client_id") or item.get("clientId") or "")
    refresh_token = str(item.get("refresh_token") or item.get("refreshToken") or "")
    if not email or not password or not client_id or not refresh_token:
        return None
    session_info = item.get("session_info") or item.get("sessionInfo")
    if not isinstance(session_info, dict):
        session_info = None
    status = str(item.get("status") or "idle")
    if status == "running":
        status = "idle"
    return AccountRow(
        id=str(item.get("id") or secrets.token_urlsafe(8)),
        email=email,
        password=password,
        client_id=client_id,
        refresh_token=refresh_token,
        material=str(item.get("material") or "----".join([email, password, client_id, refresh_token])),
        status=status,
        selected=bool(item.get("selected", True)),
        error=str(item.get("error") or ""),
        otp=str(item.get("otp") or ""),
        exported_formats=list(item.get("exported_formats") or item.get("exportedFormats") or []),
        files=list(item.get("files") or []),
        session_info=session_info,
        updated_at=str(item.get("updated_at") or item.get("updatedAt") or now_iso()),
        running_job_id=None,
    )


def parse_material_line(line: str) -> OutlookAccount:
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", line)
    if not email_match:
        raise ValueError("未找到邮箱")
    line = line[email_match.start():].strip()
    parts = [item.strip() for item in line.split("----")]
    if len(parts) != 4:
        raise ValueError("邮箱素材必须是 email----password----clientId----refreshToken 四段")
    email, password, client_id, refresh_token = parts
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ValueError("邮箱格式不正确")
    missing = [
        name
        for name, value in (
            ("password", password),
            ("clientId", client_id),
            ("refreshToken", refresh_token),
        )
        if not value
    ]
    if missing:
        raise ValueError("缺少字段: " + ", ".join(missing))
    return OutlookAccount(email=email, password=password, client_id=client_id, refresh_token=refresh_token)


def parse_bulk_material(text: str) -> tuple[list[OutlookAccount], int]:
    accounts: list[OutlookAccount] = []
    skipped = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            accounts.append(parse_material_line(line))
        except ValueError:
            skipped += 1
    if not accounts:
        raise ValueError("没有可导入的账号素材")
    return accounts, skipped


def row_to_public(row: AccountRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "email": row.email,
        "password": row.password,
        "clientId": row.client_id,
        "refreshToken": row.refresh_token,
        "material": row.material,
        "status": row.status,
        "statusLabel": ACCOUNT_STATUSES.get(row.status, row.status),
        "selected": row.selected,
        "error": row.error,
        "otp": row.otp,
        "exportedFormats": row.exported_formats,
        "files": row.files,
        "hasSession": bool(row.session_info),
        "sessionInfo": row.session_info,
        "updatedAt": row.updated_at,
        "runningJobId": row.running_job_id,
    }


def job_to_public(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "rowId": job.row_id,
        "email": job.email,
        "format": job.format,
        "status": job.status,
        "logs": job.logs[-200:],
        "files": job.files,
        "error": job.error,
        "createdAt": job.created_at,
    }


def snapshot(client_id: str) -> dict[str, Any]:
    with LOCK:
        rows_store = rows_for_client(client_id)
        jobs_store = jobs_for_client(client_id)
        rows = [row_to_public(row) for row in rows_store.values()]
        jobs = [job_to_public(job) for job in jobs_store.values()]
    summary = {
        "all": len(rows),
        "idle": sum(1 for row in rows if row["status"] == "idle"),
        "running": sum(1 for row in rows if row["status"] == "running"),
        "success": sum(1 for row in rows if row["status"] == "success"),
        "error": sum(1 for row in rows if row["status"] == "error"),
        "selected": sum(1 for row in rows if row["selected"]),
    }
    return {"rows": rows, "jobs": jobs, "summary": summary}


def sync_client_rows(client_id: str, payload: dict[str, Any]) -> None:
    """Mirror the browser-local account cache into short-lived server memory."""
    incoming = payload.get("rows")
    if incoming is None:
        clear_client_cache_after_response(client_id)
        return
    if not isinstance(incoming, list):
        raise ValueError("rows 格式不正确")

    with LOCK:
        rows_store = rows_for_client(client_id)
        jobs_store = jobs_for_client(client_id)
        next_rows: dict[str, AccountRow] = {}
        seen: set[str] = set()

        for item in incoming:
            if not isinstance(item, dict):
                continue
            raw_id = str(item.get("id") or "")
            old = rows_store.get(raw_id) if raw_id else None

            if old and old.status == "running":
                old.selected = bool(item.get("selected", old.selected))
                old.updated_at = now_iso()
                next_rows[old.id] = old
                seen.add(old.id)
                continue

            row = account_row_from_public(item)
            if not row or row.id in seen:
                continue

            if old:
                if old.session_info and not row.session_info:
                    row.session_info = old.session_info
                    if old.status == "success":
                        row.status = "success"
                if old.otp and not row.otp:
                    row.otp = old.otp
                if old.error and not row.error and old.status == "error":
                    row.error = old.error
                    row.status = "error"

            if row.status == "success" and not row.session_info:
                row.status = "idle"
            row.running_job_id = None
            next_rows[row.id] = row
            seen.add(row.id)

        rows_store.clear()
        rows_store.update(next_rows)
        keep_jobs = {job_id: job for job_id, job in jobs_store.items() if job.row_id in rows_store}
        jobs_store.clear()
        jobs_store.update(keep_jobs)


def snapshot_payload(client_id: str, **extra: Any) -> dict[str, Any]:
    data = snapshot(client_id)
    data.update(extra)
    return data


def clear_client_cache_after_response(client_id: str) -> None:
    """Drop non-running client data so account/session cache lives in the browser."""
    with LOCK:
        store = CLIENTS.get(client_id)
        if not store:
            return
        rows_store: dict[str, AccountRow] = store["rows"]  # type: ignore[assignment]
        jobs_store: dict[str, Job] = store["jobs"]  # type: ignore[assignment]
        running_row_ids = {
            row_id
            for row_id, row in rows_store.items()
            if row.status == "running"
        }
        for row_id in list(rows_store):
            if row_id not in running_row_ids:
                rows_store.pop(row_id, None)

        for job_id, job in list(jobs_store.items()):
            if job.status not in {"queued", "running"}:
                jobs_store.pop(job_id, None)
            elif job.row_id not in rows_store:
                jobs_store.pop(job_id, None)

        if not rows_store and not jobs_store:
            CLIENTS.pop(client_id, None)


def schedule_client_cache_cleanup(client_id: str) -> None:
    timer = threading.Timer(COMPLETED_CACHE_TTL_SECONDS, clear_client_cache_after_response, args=(client_id,))
    timer.daemon = True
    timer.start()


def jsonify_snapshot(client_id: str, **extra: Any):
    data = snapshot_payload(client_id, **extra)
    clear_client_cache_after_response(client_id)
    return jsonify(data)


@app.after_request
def drop_non_running_client_cache(response):
    client_id = str(request.headers.get("X-Client-Id") or "").strip()
    if re.match(r"^[A-Za-z0-9_-]{24,128}$", client_id):
        try:
            clear_client_cache_after_response(client_id)
        except Exception:
            logging.exception("清理客户端临时缓存失败")
    return response


def safe_proxy_label(proxy: str | None) -> str:
    if not proxy:
        return "无"
    try:
        scheme, rest = proxy.split("://", 1)
        host = rest.split("@")[-1]
        return f"{scheme}://...@{host}"
    except Exception:
        return "已配置"


def get_cookie_value(browser_session: BrowserSession, name: str) -> str | None:
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


def update_row(client_id: str, row_id: str, **changes: Any) -> None:
    with LOCK:
        row = rows_for_client(client_id)[row_id]
        for key, value in changes.items():
            setattr(row, key, value)
        row.updated_at = now_iso()


def log_job(job: Job, message: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')} {message}"
    with LOCK:
        job.logs.append(line)
    logging.info("[web:%s] %s", job.id, message)


def login_fetch_session(account: OutlookAccount, job: Job, row_id: str) -> dict:
    session = BrowserSession()
    log_job(job, f"创建登录会话，代理={safe_proxy_label(session.proxy)}")

    log_job(job, "连接 ChatGPT，获取 providers")
    get_providers(session)
    time.sleep(0.5)

    log_job(job, "获取 CSRF token")
    csrf_token = get_csrf_token(session)
    time.sleep(0.5)

    log_job(job, f"发起登录请求: {account.email}")
    authorize_url = signin_openai(session, csrf_token, account.email)
    otp_after_ts = time.time()
    time.sleep(0.5)

    log_job(job, "跟随授权页，触发邮箱验证码")
    follow_authorize(session, authorize_url)
    time.sleep(1)

    log_job(job, "准备验证码提交所需 Sentinel token")
    sentinel_resp = request_sentinel_token(session, "authorize_continue")
    sentinel_header, _ = build_sentinel_header(session, sentinel_resp, "authorize_continue")

    log_job(job, "轮询 Outlook 收件箱，等待 OpenAI 验证码")
    otp_code = fetch_otp_with_account(account, after_ts=otp_after_ts)
    update_row(job.client_id, row_id, otp=otp_code)
    log_job(job, f"收到邮箱验证码: {otp_code}")

    log_job(job, "提交邮箱验证码")
    validate_result = validate_email_otp(session, otp_code, sentinel_header)
    continue_url = validate_result.get("continue_url")
    page_type = (validate_result.get("page") or {}).get("type")
    if not continue_url:
        raise RuntimeError(f"验证码已提交，但响应缺少 continue_url: {validate_result}")
    if page_type == "about_you":
        raise RuntimeError("这个邮箱像是未完成 ChatGPT 注册，登录后进入 about-you。请先注册完成后再导出 session。")

    log_job(job, "完成 OAuth 回调，建立 chatgpt.com 登录态")
    headers = session.get_auth_navigate_headers(referer="https://auth.openai.com/email-verification")
    session.get(continue_url, headers=headers, allow_redirects=True)
    time.sleep(1)

    log_job(job, "读取 /api/auth/session")
    session_info = fetch_session(session)
    session_token = get_cookie_value(session, "__Secure-next-auth.session-token")
    if session_token:
        session_info["sessionToken"] = session_token
    session_info.setdefault("authProvider", "openai")
    return session_info


def run_account_job(job: Job) -> None:
    try:
        with LOCK:
            rows_store = rows_for_client(job.client_id)
            row = rows_store[job.row_id]
            account = OutlookAccount(
                email=row.email,
                password=row.password,
                client_id=row.client_id,
                refresh_token=row.refresh_token,
            )
            row.status = "running"
            row.error = ""
            row.running_job_id = job.id
            row.updated_at = now_iso()
            job.status = "running"

        session_info = login_fetch_session(account, job, job.row_id)
        log_job(job, "登录成功，Session 已缓存，等待手动导出")

        with LOCK:
            row = rows_for_client(job.client_id)[job.row_id]
            row.status = "success"
            row.error = ""
            row.files = []
            row.exported_formats = []
            row.session_info = session_info
            row.running_job_id = None
            row.updated_at = now_iso()
            job.status = "done"
        schedule_client_cache_cleanup(job.client_id)
        log_job(job, "完成")
    except Exception as exc:
        with LOCK:
            row = rows_for_client(job.client_id).get(job.row_id)
            if row:
                row.status = "error"
                row.error = public_error_message(exc)
                row.running_job_id = None
                row.updated_at = now_iso()
            job.status = "error"
            job.error = public_error_message(exc)
        schedule_client_cache_cleanup(job.client_id)
        log_job(job, f"失败: {public_error_message(exc)}")


def build_zip_bytes(files: list[tuple[str, Any]]) -> bytes:
    buffer = BytesIO()
    used_names: dict[str, int] = {}
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for raw_name, document in files:
            count = used_names.get(raw_name, 0)
            used_names[raw_name] = count + 1
            name = raw_name
            if count:
                stem, dot, suffix = raw_name.rpartition(".")
                name = f"{stem}-{count + 1}{dot}{suffix}" if dot else f"{raw_name}-{count + 1}"
            archive.writestr(name, json.dumps(document, ensure_ascii=False, indent=2) + "\n")
    return buffer.getvalue()


def build_export_files(rows: list[AccountRow], output_format: str) -> list[tuple[str, Any]]:
    output_format = normalize_output_format(output_format)
    if output_format not in (*FORMATS, "all"):
        raise ValueError("不支持的导出格式")
    missing = [row.email for row in rows if not row.session_info]
    if missing:
        raise ValueError("以下账号还没有成功登录: " + ", ".join(missing[:5]))

    now = datetime.now(timezone.utc)
    converted = [
        convert_session(row.session_info or {}, now=now, source_name=row.email, source_path="$")
        for row in rows
    ]
    files: list[tuple[str, Any]] = []
    formats = FORMATS if output_format == "all" else (output_format,)
    for fmt in formats:
        if fmt == "sub2api":
            document = build_output_document(converted, fmt, now)
            files.append(("sub2api.json", document))
            continue
        for row, item in zip(rows, converted, strict=False):
            document = build_output_document([item], fmt, now)
            base = sanitize_file_token(row.email)
            files.append((f"{base}.{fmt}.json", document))
    return files


def send_json_download(filename: str, document: Any):
    payload = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
    return send_file(
        BytesIO(payload),
        mimetype="application/json",
        as_attachment=True,
        download_name=filename,
    )


def send_zip_download(filename: str, files: list[tuple[str, Any]]):
    return send_file(
        BytesIO(build_zip_bytes(files)),
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
    )


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Codex凭证管理</title>
  <style>
    :root {
      --bg-a: #eff4ff;
      --bg-b: #f9fbff;
      --surface: rgba(255,255,255,0.92);
      --surface-strong: #ffffff;
      --text: #172033;
      --muted: #6a7893;
      --line: rgba(167, 183, 214, 0.32);
      --shadow: 0 22px 50px rgba(84, 102, 152, 0.12);
      --blue: #4f46e5;
      --blue-2: #2563eb;
      --teal: #0f9f8f;
      --red: #ef5a72;
      --red-soft: rgba(239, 90, 114, 0.12);
      --green: #15a36f;
      --green-soft: rgba(21, 163, 111, 0.12);
      --amber: #d97706;
      --amber-soft: rgba(217, 119, 6, 0.14);
      --card-radius: 28px;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--text);
      font-family: "PingFang SC", "SF Pro Display", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(120, 151, 255, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(39, 201, 167, 0.16), transparent 24%),
        linear-gradient(180deg, var(--bg-a), var(--bg-b));
      min-height: 100vh;
    }
    .shell {
      width: min(1540px, calc(100vw - 34px));
      margin: 22px auto 34px;
      display: grid;
      gap: 18px;
    }
    .panel {
      border: 1px solid var(--line);
      border-radius: var(--card-radius);
      background: var(--surface);
      backdrop-filter: blur(14px);
      box-shadow: var(--shadow);
    }
    .hero {
      padding: 26px 28px 20px;
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(440px, 0.9fr);
      gap: 20px;
      align-items: start;
    }
    .hero h1 {
      margin: 0;
      font-size: clamp(34px, 4vw, 56px);
      line-height: 1;
      letter-spacing: 0;
      font-weight: 900;
    }
    .hero-sub {
      margin-top: 14px;
      color: var(--muted);
      font-size: 15px;
    }
    .stats {
      margin-top: 18px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .chip {
      min-height: 38px;
      padding: 0 14px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line);
      color: #5c6987;
      background: rgba(255,255,255,0.8);
      font-weight: 700;
      gap: 6px;
    }
    .hero-side {
      display: grid;
      gap: 14px;
      justify-items: end;
    }
    .tabs,
    .display-pills {
      display: inline-flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      padding: 8px;
      border-radius: 22px;
      background: rgba(255,255,255,0.92);
      border: 1px solid var(--line);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.9);
    }
    .tab,
    .pill {
      min-height: 46px;
      padding: 0 22px;
      border-radius: 16px;
      border: 1px solid transparent;
      background: transparent;
      color: #5b6783;
      font-weight: 800;
      cursor: pointer;
      transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
    }
    .tab:active,
    .pill:active,
    .button:active,
    .tiny:active {
      transform: translateY(1px) scale(0.98);
    }
    .tab.active {
      color: #fff;
      background: linear-gradient(135deg, var(--blue), var(--teal));
      box-shadow: 0 14px 32px rgba(79, 70, 229, 0.24);
    }
    .pill.active {
      color: var(--blue);
      background: rgba(79, 70, 229, 0.1);
      border-color: rgba(79, 70, 229, 0.18);
    }
    .toolbar {
      padding: 20px 22px;
      display: grid;
      gap: 18px;
    }
    .toolbar-row {
      display: grid;
      grid-template-columns: 1.35fr 260px;
      gap: 16px;
      align-items: center;
    }
    .search,
    select,
    input,
    textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.92);
      color: var(--text);
      font: inherit;
      padding: 15px 18px;
      outline: none;
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.88);
    }
    textarea {
      resize: vertical;
      min-height: 132px;
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }
    .controls {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
    }
    .control-box {
      min-height: 66px;
      padding: 10px 14px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.9);
      display: inline-flex;
      gap: 12px;
      align-items: center;
    }
    .control-box strong {
      font-size: 15px;
      color: #3f4c67;
    }
    .control-box input,
    .control-box select {
      min-width: 120px;
      min-height: 42px;
      padding: 0 14px;
      border-radius: 14px;
      font-weight: 800;
    }
    .button {
      min-height: 48px;
      padding: 0 18px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.92);
      color: #5b6783;
      font-weight: 800;
      cursor: pointer;
    }
    .button.primary {
      background: linear-gradient(135deg, var(--blue), var(--teal));
      color: #fff;
      border-color: transparent;
      box-shadow: 0 16px 30px rgba(79, 70, 229, 0.22);
    }
    .button.secondary {
      background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(242,247,255,0.95));
    }
    .button.danger {
      color: var(--red);
      background: rgba(255,255,255,0.92);
      border-color: rgba(239, 90, 114, 0.22);
    }
    .button:disabled {
      opacity: 0.48;
      cursor: not-allowed;
      box-shadow: none;
    }
    .button.is-busy,
    .tiny.is-busy {
      pointer-events: none;
      opacity: 0.72;
      transform: translateY(1px);
      box-shadow: inset 0 0 0 999px rgba(255,255,255,0.18);
    }
    .button.is-busy::before,
    .tiny.is-busy::before {
      content: "";
      width: 12px;
      height: 12px;
      margin-right: 8px;
      border-radius: 999px;
      border: 2px solid currentColor;
      border-right-color: transparent;
      display: inline-block;
      vertical-align: -2px;
      animation: spin .75s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    .layout {
      display: block;
      gap: 18px;
    }
    .layout.logs-only {
      display: grid;
      grid-template-columns: 1fr;
    }
    .layout.logs-only #table-view {
      display: none;
    }
    .layout:not(.logs-only) .side-panel {
      display: none;
    }
    .table-wrap {
      padding: 12px 0 0;
      overflow: auto;
    }
    table {
      width: 100%;
      min-width: 1120px;
      border-collapse: collapse;
      table-layout: fixed;
    }
    thead th {
      position: sticky;
      top: 0;
      background: rgba(247, 250, 255, 0.96);
      z-index: 1;
      font-size: 13px;
      color: #6c7a96;
      text-align: left;
      padding: 18px 16px;
      border-bottom: 1px solid rgba(174, 190, 219, 0.28);
    }
    tbody td {
      padding: 14px 16px;
      border-bottom: 1px solid rgba(228, 234, 246, 0.85);
      vertical-align: middle;
      font-size: 14px;
    }
    tbody tr:hover td {
      background: rgba(245, 248, 255, 0.88);
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 84px;
      min-height: 34px;
      border-radius: 999px;
      padding: 0 12px;
      font-weight: 800;
      font-size: 13px;
    }
    .status-idle { background: rgba(108, 122, 150, 0.12); color: #66748f; }
    .status-running { background: var(--amber-soft); color: var(--amber); }
    .status-success { background: var(--green-soft); color: var(--green); }
    .status-error { background: var(--red-soft); color: var(--red); }
    .mono {
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }
    .clip {
      display: block;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .cell-title {
      font-weight: 800;
      color: #21304f;
    }
    .cell-sub {
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      max-width: 100%;
    }
    .cell-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .tiny {
      min-height: 34px;
      padding: 0 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: #fff;
      color: #5d6a87;
      font-weight: 800;
      cursor: pointer;
    }
    .side-panel {
      padding: 18px;
    }
    .side-card {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.88);
      padding: 16px;
      display: grid;
      gap: 12px;
    }
    .side-card h3 {
      margin: 0;
      font-size: 15px;
    }
    .otp-box {
      min-height: 84px;
      border-radius: 18px;
      background: linear-gradient(135deg, rgba(79, 70, 229, 0.08), rgba(15, 159, 143, 0.12));
      border: 1px solid rgba(79, 70, 229, 0.18);
      display: grid;
      place-items: center;
      font-size: 34px;
      font-weight: 900;
      color: var(--blue);
    }
    .log {
      min-height: 420px;
      max-height: 620px;
      overflow: auto;
      border-radius: 20px;
      background: #101826;
      color: #d7e6ff;
      padding: 14px;
      white-space: pre-wrap;
      font-family: ui-monospace, "SFMono-Regular", Consolas, monospace;
      font-size: 12px;
    }
    .empty {
      padding: 80px 24px;
      text-align: center;
      color: #6f7d97;
      font-size: 24px;
      font-weight: 800;
    }
    .subline {
      color: var(--muted);
      font-size: 13px;
    }
    .status-detail {
      display: grid;
      gap: 10px;
    }
    .status-field {
      display: grid;
      gap: 4px;
    }
    .status-field label {
      font-size: 12px;
      font-weight: 800;
      color: var(--muted);
    }
    .status-field .value {
      font-size: 13px;
      word-break: break-all;
    }
    .toast-wrap {
      position: fixed;
      top: 24px;
      left: 50%;
      transform: translateX(-50%);
      z-index: 9999;
      display: grid;
      gap: 8px;
      pointer-events: none;
      width: min(520px, calc(100vw - 32px));
    }
    .toast {
      min-width: 160px;
      padding: 14px 22px;
      border-radius: 16px;
      background: rgba(23, 32, 51, 0.92);
      color: #f5f8ff;
      font-size: 14px;
      font-weight: 800;
      text-align: center;
      line-height: 1.5;
      box-shadow: 0 18px 40px rgba(23, 32, 51, 0.24);
      opacity: 0;
      transform: translateY(-12px);
      transition: opacity 0.2s ease, transform 0.2s ease;
    }
    .toast.show {
      opacity: 1;
      transform: translateY(0);
    }
    .toast.success {
      background: rgba(21, 163, 111, 0.96);
      color: #ffffff;
      box-shadow: 0 18px 40px rgba(21, 163, 111, 0.28);
    }
    .toast.error {
      background: rgba(239, 90, 114, 0.96);
      color: #ffffff;
      box-shadow: 0 18px 40px rgba(239, 90, 114, 0.28);
    }
    .row-check {
      width: 22px;
      height: 22px;
      accent-color: var(--blue);
    }
    .format-list {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .format-badge {
      min-height: 28px;
      padding: 0 10px;
      border-radius: 999px;
      background: rgba(79, 70, 229, 0.08);
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
      display: inline-flex;
      align-items: center;
    }
    @media (max-width: 1180px) {
      .hero,
      .toolbar-row {
        grid-template-columns: 1fr;
      }
      .hero-side {
        justify-items: start;
      }
      .layout.logs-only .side-panel {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 760px) {
      .shell {
        width: min(100vw - 18px, 100%);
        margin: 12px auto 22px;
      }
      .hero {
        padding: 20px 18px 18px;
      }
      .toolbar,
      .side-panel {
        padding: 14px;
      }
      thead th,
      tbody td {
        padding: 12px 10px;
      }
    }
  </style>
</head>
<body>
  <div id="toast-wrap" class="toast-wrap"></div>
  <div class="shell">
    <section class="panel hero">
      <div>
        <h1 data-i18n="title">Codex凭证管理</h1>
      </div>
      <div class="hero-side">
        <div class="display-pills">
          <button class="pill active" data-lang="zh" data-i18n="langZh">中文</button>
          <button class="pill" data-lang="en" data-i18n="langEn">English</button>
        </div>
      </div>
    </section>

    <section class="panel toolbar">
      <div class="controls">
        <div class="control-box">
          <strong data-i18n="formatLabel">导出类型</strong>
          <select id="format">
            <option value="sub2api">sub2api</option>
            <option value="cpa">cpa</option>
            <option value="cockpit">cockpit</option>
            <option value="9router">9router</option>
            <option value="axonhub">axonhub</option>
            <option value="all" data-i18n="formatAll">全部</option>
          </select>
        </div>
        <button id="read-otp" class="button secondary" data-i18n="readOtp">读取验证码</button>
        <button id="export-selected" class="button secondary" data-i18n="exportSelected">导出选中</button>
        <button id="delete-selected" class="button danger" data-i18n="deleteSelected">删除选中</button>
      </div>
    </section>

    <div class="layout" id="main-layout">
      <section class="panel" id="table-view">
        <div style="padding:18px 20px 0;">
          <div class="toolbar-row" style="grid-template-columns: minmax(0, 1fr) 140px;">
            <input id="card-key" class="search mono" placeholder="请输入卡密" data-i18n-placeholder="cardPlaceholder">
            <button id="redeem-card" class="button primary" data-i18n="redeemCard">取号</button>
          </div>
          <div class="controls" style="margin-top:12px;">
            <div class="subline" id="import-status" data-i18n="redeemHint">每枚卡密对应一个账号，取号后可登录并导出 Session。</div>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th style="width:52px;"><input id="select-all" class="row-check" type="checkbox"></th>
                <th style="width:120px;" data-i18n="colStatus">状态</th>
                <th style="width:280px;" data-i18n="colAccount">账号</th>
                <th style="width:150px;" data-i18n="colPassword">邮箱密码</th>
                <th style="width:120px;" data-i18n="colOtp">验证码</th>
                <th style="width:260px;" data-i18n="colError">错误</th>
                <th style="width:160px;" data-i18n="colExport">导出结果</th>
                <th style="width:180px;" data-i18n="colActions">操作</th>
              </tr>
            </thead>
            <tbody id="table-body"></tbody>
          </table>
        </div>
      </section>

      <aside class="panel side-panel">
        <div class="side-card">
          <h3 data-i18n="accountStatus">账号状态</h3>
          <div id="status-detail" class="status-detail">
            <div class="subline" data-i18n="statusHint">点击操作列「查看」显示当前账号状态。</div>
          </div>
        </div>
      </aside>
    </div>
  </div>

  <script>
    const state = {
      rows: [],
      jobs: [],
      summary: {},
      selectedRowId: null,
      pollTimer: null,
      importStatus: "",
      lang: localStorage.getItem("youyu-help-lang") === "en" ? "en" : "zh",
      lastError: "",
      otpBusyRowId: null,
      otpBusyToolbar: false,
    };

    const $ = (id) => document.getElementById(id);
    const STORAGE_KEY = "youyu-help-accounts-v2";
    const DELETED_IDS_KEY = "youyu-help-deleted-ids-v1";
    const CLIENT_KEY = "youyu-help-client-id";
    const LANG_KEY = "youyu-help-lang";
    const DEFAULT_CONCURRENCY = 3;

    function makeClientId() {
      const bytes = new Uint8Array(24);
      crypto.getRandomValues(bytes);
      return Array.from(bytes, (byte) => byte.toString(36).padStart(2, "0")).join("");
    }

    const clientId = (() => {
      let value = localStorage.getItem(CLIENT_KEY);
      if (!value) {
        value = makeClientId();
        localStorage.setItem(CLIENT_KEY, value);
      }
      return value;
    })();

    function loadLocalRows() {
      try {
        const rows = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
        state.rows = Array.isArray(rows) ? rows.map((row) => ({
          ...row,
          exportedFormats: row.exportedFormats || [],
          hasSession: Boolean(row.sessionInfo || row.hasSession),
        })) : [];
      } catch {
        state.rows = [];
      }
    }

    function saveLocalRows() {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state.rows));
    }

    function deletedIdSet() {
      try {
        return new Set(JSON.parse(localStorage.getItem(DELETED_IDS_KEY) || "[]"));
      } catch {
        return new Set();
      }
    }

    function rememberDeletedIds(ids) {
      const set = deletedIdSet();
      ids.forEach((id) => set.add(id));
      localStorage.setItem(DELETED_IDS_KEY, JSON.stringify([...set]));
    }

    function unforgetDeletedIds(ids) {
      const set = deletedIdSet();
      let changed = false;
      ids.forEach((id) => {
        if (set.delete(id)) changed = true;
      });
      if (changed) {
        localStorage.setItem(DELETED_IDS_KEY, JSON.stringify([...set]));
      }
    }

    function publicRowsForServer() {
      return state.rows.map((row) => ({
        id: row.id,
        email: row.email,
        password: row.password,
        clientId: row.clientId,
        refreshToken: row.refreshToken,
        material: row.material,
        status: row.status,
        selected: row.selected,
        error: row.error,
        otp: row.otp,
        exportedFormats: row.exportedFormats || [],
        files: [],
        sessionInfo: row.sessionInfo || null,
        hasSession: Boolean(row.sessionInfo || row.hasSession),
        updatedAt: row.updatedAt,
      }));
    }

    async function apiFetch(url, options = {}) {
      const headers = {
        "Content-Type": "application/json",
        "X-Client-Id": clientId,
        "X-Client-Lang": state.lang || "zh",
        ...(options.headers || {}),
      };
      return fetch(url, {...options, headers});
    }

    function mergeServerState(data) {
      const deleted = deletedIdSet();
      const localRows = new Map(state.rows.map((row) => [row.id, row]));
      state.rows = (data.rows || [])
        .filter((remote) => !deleted.has(remote.id))
        .map((remote) => {
        const local = localRows.get(remote.id) || {};
        return {
          ...local,
          ...remote,
          sessionInfo: remote.sessionInfo || local.sessionInfo || null,
          hasSession: Boolean(remote.sessionInfo || remote.hasSession || local.sessionInfo || local.hasSession),
        };
      });
      state.jobs = data.jobs || [];
      state.summary = data.summary || summarizeRows();
      if (state.selectedRowId && !state.rows.some((row) => row.id === state.selectedRowId)) {
        state.selectedRowId = null;
      }
      saveLocalRows();
    }

    function summarizeRows() {
      return {
        all: state.rows.length,
        idle: state.rows.filter((row) => row.status === "idle").length,
        running: state.rows.filter((row) => row.status === "running").length,
        success: state.rows.filter((row) => row.status === "success").length,
        error: state.rows.filter((row) => row.status === "error").length,
        selected: state.rows.filter((row) => row.selected).length,
      };
    }

    const labels = {
      zh: {
        title: "Codex凭证管理",
        subtitle: "输入后台制作的卡密领取账号，自动登录、收取验证码、拉取 Session，并按所选格式导出。",
        tableTab: "账号表格",
        logsTab: "日志",
        langZh: "中文",
        langEn: "English",
        searchPlaceholder: "搜索邮箱、错误、状态",
        statusAll: "全部状态",
        statusIdle: "待处理",
        statusRunning: "登录中",
        statusSuccess: "成功",
        statusError: "失败",
        concurrency: "并发",
        formatLabel: "导出类型",
        formatAll: "全部",
        runSelected: "登录选中",
        readOtp: "读取验证码",
        exportSelected: "导出选中",
        deleteSelected: "删除选中",
        clearLogs: "清空日志视图",
        bulkPlaceholder: "可粘贴整段素材，系统会自动跳过说明行；账号格式：email----password----clientId----refreshToken",
        cardPlaceholder: "请输入卡密",
        redeemCard: "取号",
        redeemHint: "每枚卡密对应一个账号，取号后可登录并导出 Session。",
        redeemFail: "取号失败",
        redeemToastSuccess: (email, reused) => reused ? `兑换成功，已恢复账号 ${email}` : `兑换成功：${email}`,
        redeemToastFail: (reason) => reason || "兑换失败，请检查卡密后重试",
        redeemDone: (email, reused) => reused ? `卡密已绑定账号 ${email}，已恢复显示` : `取号成功：${email}`,
        logRedeem: (email, reused) => reused ? `恢复卡密账号 ${email}` : `卡密取号 ${email}`,
        busyRedeem: "取号中",
        importAccounts: "导入账号",
        importHint: "取号后账号保存在本机浏览器，可登录并导出。",
        colStatus: "状态",
        colAccount: "导入账号",
        colPassword: "邮箱密码",
        colOtp: "验证码",
        colError: "错误",
        colExport: "导出结果",
        colActions: "操作",
        accountStatus: "账号状态",
        statusHint: "点击操作列「查看」显示当前账号状态。",
        otpSuccess: (email, otp) => `读取成功：${email} · ${otp}`,
        otpFail: (email, reason) => reason || `读取失败：${email}`,
        runLogs: "运行日志",
        waiting: "等待开始",
        statAll: "全部",
        statSelected: "已选中",
        empty: "输入卡密取号开始",
        notExported: "未导出",
        actionView: "查看",
        actionOtp: "验证码",
        actionRun: "登录",
        actionRetry: "重试",
        importFail: "导入失败",
        importDone: (imported, skipped) => `已导入 ${imported} 个账号${skipped ? `，跳过 ${skipped} 行` : ""}`,
        logImport: (imported, skipped) => `导入账号 ${imported} 个${skipped ? `，跳过 ${skipped} 行` : ""}`,
        opFail: "操作失败",
        readFail: "读取失败",
        logOtp: (email, otp) => `读取验证码 ${email}: ${otp}`,
        startFail: "启动失败",
        logStart: (started, concurrency) => `开始批量任务 ${started} 个，并发 ${concurrency}`,
        noFiles: "请先勾选要导出的账号",
        exportNotReady: "账号尚未就绪，请重新取号或联系管理员",
        logDownload: (count) => `下载 ${count} 个账号的导出文件`,
        logExport: (count, format) => `导出 ${count} 个账号，格式 ${format}`,
        exportFail: "导出失败",
        busyImport: "导入中",
        busyLogin: "登录中",
        busyOtp: "读取中",
        busyExport: "导出中",
        busyDelete: "删除中",
        chooseOne: "请先选择一个账号",
        chooseAccounts: "请先勾选账号",
        noSelected: "没有选中的账号",
        logDelete: (count) => `删除账号 ${count} 个`,
      },
      en: {
        title: "Codex Credential Console",
        subtitle: "Enter an admin card key to claim an account, then log in automatically and export the selected Session format.",
        tableTab: "Accounts",
        logsTab: "Logs",
        langZh: "中文",
        langEn: "English",
        searchPlaceholder: "Search email, error, status",
        statusAll: "All statuses",
        statusIdle: "Idle",
        statusRunning: "Running",
        statusSuccess: "Success",
        statusError: "Failed",
        concurrency: "Concurrency",
        formatLabel: "Export format",
        formatAll: "All",
        runSelected: "Run Selected",
        readOtp: "Read OTP",
        exportSelected: "Export Selected",
        deleteSelected: "Delete Selected",
        clearLogs: "Clear Logs",
        bulkPlaceholder: "Paste a whole block; non-account lines are skipped. Format: email----password----clientId----refreshToken",
        cardPlaceholder: "Please enter card key",
        redeemCard: "Claim",
        redeemHint: "Each card key maps to one account. After claiming, you can log in and export Session.",
        redeemFail: "Claim failed",
        redeemToastSuccess: (email, reused) => reused ? `Claimed successfully, restored ${email}` : `Claimed successfully: ${email}`,
        redeemToastFail: (reason) => reason || "Claim failed. Please check the card key and try again.",
        redeemDone: (email, reused) => reused ? `Card already bound to ${email}; restored` : `Claimed account: ${email}`,
        logRedeem: (email, reused) => reused ? `Restored card account ${email}` : `Claimed account ${email}`,
        busyRedeem: "Claiming",
        importAccounts: "Import Accounts",
        importHint: "Claimed accounts stay in this browser only. You can log in and export locally.",
        colStatus: "Status",
        colAccount: "Account",
        colPassword: "Mailbox Password",
        colOtp: "OTP",
        colError: "Error",
        colExport: "Exports",
        colActions: "Actions",
        accountStatus: "Account Status",
        statusHint: "Click View in the Actions column to inspect the current account.",
        otpSuccess: (email, otp) => `OTP read OK: ${email} · ${otp}`,
        otpFail: (email, reason) => reason || `OTP read failed: ${email}`,
        runLogs: "Run Logs",
        waiting: "Waiting",
        statAll: "All",
        statSelected: "Selected",
        empty: "Enter a card key to start",
        notExported: "Not exported",
        actionView: "View",
        actionOtp: "OTP",
        actionRun: "Run",
        actionRetry: "Retry",
        importFail: "Import failed",
        importDone: (imported, skipped) => `Imported ${imported} account${imported === 1 ? "" : "s"}${skipped ? `, skipped ${skipped} line${skipped === 1 ? "" : "s"}` : ""}`,
        logImport: (imported, skipped) => `Imported ${imported} account${imported === 1 ? "" : "s"}${skipped ? `, skipped ${skipped} line${skipped === 1 ? "" : "s"}` : ""}`,
        opFail: "Operation failed",
        readFail: "Read failed",
        logOtp: (email, otp) => `Read OTP ${email}: ${otp}`,
        startFail: "Start failed",
        logStart: (started, concurrency) => `Started ${started} job${started === 1 ? "" : "s"} with concurrency ${concurrency}`,
        noFiles: "Select accounts to export first",
        exportNotReady: "Account not ready yet; reclaim the card or contact admin",
        logDownload: (count) => `Downloading files for ${count} account${count === 1 ? "" : "s"}`,
        logExport: (count, format) => `Exporting ${count} account${count === 1 ? "" : "s"} as ${format}`,
        exportFail: "Export failed",
        busyImport: "Importing",
        busyLogin: "Logging in",
        busyOtp: "Reading",
        busyExport: "Exporting",
        busyDelete: "Deleting",
        chooseOne: "Select one account first",
        chooseAccounts: "Tick accounts first",
        noSelected: "No selected accounts",
        logDelete: (count) => `Deleted ${count} account${count === 1 ? "" : "s"}`,
      },
    };

    const t = (key) => (labels[state.lang] && labels[state.lang][key]) || labels.zh[key] || key;

    const ERROR_ZH_MAP = {
      "cannot rollback - no transaction is active": "系统繁忙，请稍后重试",
      "database is locked": "数据库繁忙，请稍后重试",
      "database disk image is malformed": "数据库异常，请联系管理员",
      "unique constraint failed": "数据冲突，请刷新后重试",
    };

    const ERROR_ZH_TO_EN = {
      "卡密不存在": "Card key not found",
      "卡密已被使用": "Card key has already been used",
      "卡密不能为空": "Card key cannot be empty",
      "卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位": "Invalid card key format: PP uses Codex-P + 20 chars, GO uses Codex-G + 20 chars",
      "卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位（旧版 Codex- + 16 位仍可用）": "Invalid card key format: PP uses Codex-P + 20 chars, GO uses Codex-G + 20 chars (legacy Codex- + 16 chars still supported)",
      "缺少或非法 client id": "Missing or invalid client id",
      "未找到邮箱": "Email not found",
      "没有可运行的账号": "No runnable accounts",
      "不支持的导出格式": "Unsupported export format",
      "系统繁忙，请稍后重试": "System is busy. Please try again later.",
      "数据库繁忙，请稍后重试": "Database is busy. Please try again later.",
      "操作失败，请稍后重试": "Operation failed. Please try again.",
      "读取失败：验证码已超过2分钟": "Failed to read OTP: code is older than 2 minutes",
      "读取失败：2分钟内未收到验证码": "Failed to read OTP: no code received within 2 minutes",
      "读取失败：未知错误": "Failed to read OTP: unknown error",
    };

    const ERROR_ZH_PATTERNS = [
      [/^暂无 (PP|GO) 测试通过的可用账号，请稍后再试或联系管理员$/, (m) => `No available ${m[1]} accounts that passed testing. Please try again later or contact the administrator.`],
      [/^卡密类型不匹配：该卡密属于 (PP|GO) 池$/, (m) => `Card key type mismatch: this key belongs to the ${m[1]} pool.`],
      [/^读取失败：(.+)$/, (m) => `Failed to read OTP: ${m[1]}`],
    ];

    function localizeError(message) {
      const text = String(message || "").trim();
      if (!text) return state.lang === "en" ? "Operation failed. Please try again." : "操作失败，请稍后重试";
      if (state.lang === "en") {
        if (!/[\u4e00-\u9fff]/.test(text)) return text;
        if (ERROR_ZH_TO_EN[text]) return ERROR_ZH_TO_EN[text];
        for (const [pattern, format] of ERROR_ZH_PATTERNS) {
          const match = text.match(pattern);
          if (match) return format(match);
        }
        return "Operation failed. Please try again.";
      }
      if (/[\u4e00-\u9fff]/.test(text)) return text;
      const lowered = text.toLowerCase();
      for (const [key, value] of Object.entries(ERROR_ZH_MAP)) {
        if (lowered.includes(key)) return value;
      }
      return "操作失败，请稍后重试";
    }

    function statusLabel(row) {
      const map = {
        idle: "statusIdle",
        running: "statusRunning",
        success: "statusSuccess",
        error: "statusError",
      };
      return t(map[row.status] || "") || row.statusLabel || row.status || "";
    }

    function statusClass(status) {
      return `status-${status || 'idle'}`;
    }

    function appendManualLog(_text) {}

    function showToast(message, type = "info", durationMs = 0) {
      const wrap = $("toast-wrap");
      wrap.innerHTML = "";
      const node = document.createElement("div");
      node.className = `toast ${type === "success" ? "success" : type === "error" ? "error" : ""}`;
      node.textContent = type === "error" ? localizeError(message) : String(message || "");
      wrap.appendChild(node);
      const stayMs = durationMs || (type === "error" ? 4500 : 3000);
      requestAnimationFrame(() => node.classList.add("show"));
      setTimeout(() => {
        node.classList.remove("show");
        setTimeout(() => node.remove(), 220);
      }, stayMs);
    }

    function renderLogs() {}

    async function withBusy(button, busyText, task) {
      if (!button) return task();
      const originalText = button.textContent;
      button.disabled = true;
      button.classList.add("is-busy");
      if (busyText) button.textContent = busyText;
      try {
        return await task();
      } finally {
        button.disabled = false;
        button.classList.remove("is-busy");
        button.textContent = originalText;
      }
    }

    function selectedRows() {
      return state.rows.filter((row) => row.selected);
    }

    function activeFormat() {
      return $("format").value;
    }

    function activeConcurrency() {
      return DEFAULT_CONCURRENCY;
    }

    function selectedRow() {
      return state.rows.find((row) => row.id === state.selectedRowId) || null;
    }

    function applyLanguage() {
      document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
      document.title = t("title");
      document.querySelectorAll("[data-i18n]").forEach((node) => {
        node.textContent = t(node.dataset.i18n);
      });
      document.querySelectorAll("[data-i18n-placeholder]").forEach((node) => {
        node.placeholder = t(node.dataset.i18nPlaceholder);
      });
      document.querySelectorAll("[data-lang]").forEach((item) => {
        item.classList.toggle("active", item.dataset.lang === state.lang);
      });
      $("import-status").textContent = state.lastError
        ? localizeError(state.lastError)
        : (state.importStatus || t("importHint"));
      updateBusyButtons();
    }

    function updateBusyButtons() {
      const topBtn = $("read-otp");
      if (!topBtn) return;
      const busy = Boolean(state.otpBusyToolbar);
      topBtn.disabled = busy;
      topBtn.classList.toggle("is-busy", busy);
      topBtn.textContent = busy ? t("busyOtp") : t("readOtp");
    }

    function render() {
      applyLanguage();
      renderRows();
      renderStatusCard();
    }

    function renderRows() {
      const rows = state.rows;
      $("select-all").checked = rows.length > 0 && rows.every((row) => row.selected);
      $("select-all").indeterminate = rows.some((row) => row.selected) && !rows.every((row) => row.selected);
      if (!rows.length) {
        $("table-body").innerHTML = `<tr><td colspan="8" class="empty">${t("empty")}</td></tr>`;
        return;
      }
      $("table-body").innerHTML = rows.map((row) => `
        <tr data-row-id="${row.id}">
          <td><input class="row-check row-selector" type="checkbox" data-row-id="${row.id}" ${row.selected ? "checked" : ""}></td>
          <td><span class="status-pill ${statusClass(row.status)}">${statusLabel(row)}</span></td>
          <td>
            <div class="cell-title clip" title="${row.email}">${row.email}</div>
            <div class="cell-sub mono" title="${row.clientId}">${row.clientId}</div>
          </td>
          <td><span class="mono clip" title="${row.password || "-"}">${row.password || "-"}</span></td>
          <td><span class="mono clip" title="${row.otp || "-"}">${row.otp || "-"}</span></td>
          <td>
            <div class="cell-sub" title="${localizeError(row.error || "-")}">${localizeError(row.error || "-")}</div>
          </td>
          <td>
            <div class="format-list">
              ${(row.exportedFormats || []).length ? row.exportedFormats.map((fmt) => `<span class="format-badge">${fmt}</span>`).join("") : `<span class="cell-sub">${t("notExported")}</span>`}
            </div>
          </td>
          <td>
            <div class="cell-actions">
              <button class="tiny act-view" data-row-id="${row.id}">${t("actionView")}</button>
              <button class="tiny act-otp${state.otpBusyRowId === row.id ? " is-busy" : ""}" data-row-id="${row.id}" ${state.otpBusyRowId === row.id ? "disabled" : ""}>${state.otpBusyRowId === row.id ? t("busyOtp") : t("actionOtp")}</button>
            </div>
          </td>
        </tr>
      `).join("");
    }

    function renderStatusCard() {
      const row = selectedRow();
      const detail = $("status-detail");
      if (!row) {
        detail.innerHTML = `<div class="subline">${t("statusHint")}</div>`;
        return;
      }
      const exports = (row.exportedFormats || []).length
        ? row.exportedFormats.map((fmt) => `<span class="format-badge">${fmt}</span>`).join("")
        : t("notExported");
      detail.innerHTML = `
        <div><span class="status-pill ${statusClass(row.status)}">${statusLabel(row)}</span></div>
        <div class="status-field">
          <label>${t("colAccount")}</label>
          <div class="value">${row.email || "-"}</div>
          <div class="cell-sub mono">${row.clientId || "-"}</div>
        </div>
        <div class="status-field">
          <label>${t("colPassword")}</label>
          <div class="value mono">${row.password || "-"}</div>
        </div>
        <div class="status-field">
          <label>${t("colOtp")}</label>
          <div class="value mono">${row.otp || "-"}</div>
        </div>
        <div class="status-field">
          <label>${t("colError")}</label>
          <div class="value">${localizeError(row.error || "-")}</div>
        </div>
        <div class="status-field">
          <label>${t("colExport")}</label>
          <div class="value format-list">${exports}</div>
        </div>
      `;
    }

    async function fetchState() {
      const res = await apiFetch("/api/state", {
        method: "POST",
        body: JSON.stringify({ rows: publicRowsForServer() }),
      });
      const data = await res.json();
      mergeServerState(data);
      if (state.selectedRowId && !state.rows.some((row) => row.id === state.selectedRowId)) {
        state.selectedRowId = null;
      }
      render();
    }

    async function redeemCardKey() {
      const cardKey = $("card-key").value.trim();
      if (!cardKey) throw new Error(t("cardPlaceholder"));
      const res = await apiFetch("/api/redeem", {
        method: "POST",
        body: JSON.stringify({ card_key: cardKey, rows: publicRowsForServer() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("redeemFail"));
      const restoreIds = new Set(
        (data.rows || []).map((row) => row.id).filter(Boolean),
      );
      if (data.accountId) restoreIds.add(data.accountId);
      if (data.id) restoreIds.add(data.id);
      unforgetDeletedIds([...restoreIds]);
      mergeServerState(data);
      if (!state.rows.length && (data.rows || []).length) {
        state.rows = (data.rows || []).map((remote) => ({
          exportedFormats: [],
          hasSession: false,
          ...remote,
          sessionInfo: remote.sessionInfo || null,
          hasSession: Boolean(remote.sessionInfo || remote.hasSession),
          selected: true,
        }));
        saveLocalRows();
      }
      $("card-key").value = "";
      state.lastError = "";
      state.importStatus = t("redeemDone")(data.email || "", Boolean(data.reused));
      $("import-status").textContent = state.importStatus;
      showToast(t("redeemToastSuccess")(data.email || "", Boolean(data.reused)), "success");
      appendManualLog(t("logRedeem")(data.email || "", Boolean(data.reused)));
      render();
    }

    async function patchRows(payload) {
      const res = await apiFetch("/api/accounts/patch", {
        method: "POST",
        body: JSON.stringify({...payload, rows: publicRowsForServer()}),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("opFail"));
      mergeServerState(data);
      render();
      return data;
    }

    async function readOtp(rowId, options = {}) {
      const row = state.rows.find((item) => item.id === rowId);
      const email = row?.email || "";
      state.otpBusyRowId = rowId;
      if (options.toolbar) state.otpBusyToolbar = true;
      renderRows();
      updateBusyButtons();
      try {
        const res = await apiFetch("/api/otp", {
          method: "POST",
          body: JSON.stringify({ row_id: rowId, rows: publicRowsForServer() }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || t("readFail"));
        mergeServerState(data);
        showToast(t("otpSuccess")(data.email || email, data.otp || "-"), "success");
        render();
      } catch (error) {
        const reason = error?.message || t("readFail");
        showToast(t("otpFail")(email, reason), "error");
        throw error;
      } finally {
        state.otpBusyRowId = null;
        state.otpBusyToolbar = false;
        renderRows();
        updateBusyButtons();
        if (state.selectedRowId === rowId) {
          renderStatusCard();
        }
      }
    }

    async function runSelected(rowIds) {
      const res = await apiFetch("/api/run", {
        method: "POST",
        body: JSON.stringify({
          row_ids: rowIds,
          format: activeFormat(),
          concurrency: activeConcurrency(),
          rows: publicRowsForServer(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("startFail"));
      mergeServerState(data);
      appendManualLog(t("logStart")(data.started, data.concurrency));
      startPolling();
      render();
    }

    async function exportSelected() {
      const rows = selectedRows().filter((row) => row.hasSession || row.sessionInfo);
      if (!rows.length) {
        const picked = selectedRows();
        throw new Error(picked.length ? t("exportNotReady") : t("noFiles"));
      }
      const outputFormat = activeFormat();
      appendManualLog(t("logExport")(rows.length, outputFormat));
      const res = await apiFetch("/api/export", {
        method: "POST",
        body: JSON.stringify({
          row_ids: rows.map((row) => row.id),
          format: outputFormat,
          rows: publicRowsForServer(),
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || t("exportFail"));
      mergeServerState(data);
      const filename = data.filename || `${outputFormat}-export.json`;
      const contentBase64 = data.contentBase64 || "";
      if (!contentBase64) throw new Error(t("exportFail"));
      const binary = atob(contentBase64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: data.mimeType || "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      render();
      appendManualLog(t("logDownload")(rows.length));
    }

    function startPolling() {
      if (state.pollTimer) return;
      state.pollTimer = setInterval(async () => {
        await fetchState();
        const stillRunning = state.rows.some((row) => row.status === "running") || state.jobs.some((job) => job.status === "queued" || job.status === "running");
        if (!stillRunning) {
          clearInterval(state.pollTimer);
          state.pollTimer = null;
        }
      }, 1600);
    }

    $("redeem-card").addEventListener("click", async () => {
      await withBusy($("redeem-card"), t("busyRedeem"), async () => {
        try {
          await redeemCardKey();
        } catch (error) {
          state.lastError = error.message || t("redeemFail");
          const message = localizeError(state.lastError);
          state.importStatus = message;
          $("import-status").textContent = message;
          showToast(t("redeemToastFail")(message), "error");
        }
      });
    });

    $("card-key").addEventListener("keydown", async (event) => {
      if (event.key !== "Enter") return;
      event.preventDefault();
      $("redeem-card").click();
    });

    $("select-all").addEventListener("change", async (event) => {
      const selected = event.target.checked;
      state.rows = state.rows.map((row) => ({...row, selected}));
      saveLocalRows();
      render();
    });

    $("table-body").addEventListener("click", async (event) => {
      const rowId = event.target.dataset.rowId;
      if (!rowId) return;
      if (event.target.classList.contains("act-view")) {
        state.selectedRowId = rowId;
        render();
        return;
      }
      if (event.target.classList.contains("act-otp")) {
        if (state.otpBusyRowId) return;
        state.selectedRowId = rowId;
        renderStatusCard();
        try {
          await readOtp(rowId);
        } catch (_error) {}
      }
    });

    $("table-body").addEventListener("change", async (event) => {
      if (!event.target.classList.contains("row-selector")) return;
      const rowId = event.target.dataset.rowId;
      state.rows = state.rows.map((row) => row.id === rowId ? {...row, selected: event.target.checked} : row);
      saveLocalRows();
      render();
    });

    $("read-otp").addEventListener("click", async () => {
      if (state.otpBusyToolbar || state.otpBusyRowId) return;
      const row = selectedRow() || selectedRows()[0];
      if (!row) {
        showToast(t("chooseOne"), "error");
        return;
      }
      state.selectedRowId = row.id;
      renderStatusCard();
      try {
        await readOtp(row.id, { toolbar: true });
      } catch (_error) {}
    });

    $("delete-selected").addEventListener("click", async () => {
      const ids = selectedRows().map((row) => row.id);
      if (!ids.length) {
        return;
      }
      await withBusy($("delete-selected"), t("busyDelete"), async () => {
        rememberDeletedIds(ids);
        const idSet = new Set(ids);
        state.rows = state.rows.filter((row) => !idSet.has(row.id));
        if (state.selectedRowId && idSet.has(state.selectedRowId)) {
          state.selectedRowId = null;
        }
        saveLocalRows();
        render();
      });
    });

    $("export-selected").addEventListener("click", async () => {
      const rows = selectedRows();
      if (!rows.length) {
        showToast(t("noFiles"), "error");
        return;
      }
      await withBusy($("export-selected"), t("busyExport"), async () => {
        try {
          await exportSelected();
        } catch (error) {
          showToast(error.message || t("exportFail"), "error", 5000);
        }
      });
    });

    document.querySelectorAll("[data-lang]").forEach((button) => {
      button.addEventListener("click", () => {
        state.lang = button.dataset.lang || "zh";
        localStorage.setItem(LANG_KEY, state.lang);
        render();
      });
    });

    loadLocalRows();
    render();
    fetchState();
  </script>
</body>
</html>
"""


@app.get("/")
def index():
    return Response(
        HTML,
        mimetype="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Build-Id": str(ADMIN_BUILD_ID),
        },
    )


@app.get("/api/state")
def api_state():
    return jsonify({"rows": [], "jobs": [], "summary": {"all": 0, "idle": 0, "running": 0, "success": 0, "error": 0, "selected": 0}})


@app.post("/api/state")
def api_state_post():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify_snapshot(client_id)


@app.post("/api/accounts/import")
def import_accounts():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
        accounts, skipped = parse_bulk_material(payload.get("material") or "")
    except Exception as exc:
        return api_error_response(exc)

    imported = 0
    with LOCK:
        rows_store = rows_for_client(client_id)
        existing_emails = {row.email.lower() for row in rows_store.values()}
        for account in accounts:
            if account.email.lower() in existing_emails:
                continue
            row_id = secrets.token_urlsafe(8)
            rows_store[row_id] = AccountRow(
                id=row_id,
                email=account.email,
                password=account.password,
                client_id=account.client_id,
                refresh_token=account.refresh_token,
                material="----".join([account.email, account.password, account.client_id, account.refresh_token]),
            )
            existing_emails.add(account.email.lower())
            imported += 1
    return jsonify_snapshot(client_id, imported=imported, skipped=skipped)


@app.post("/api/accounts/patch")
def patch_accounts():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
    except Exception as exc:
        return api_error_response(exc)
    action = payload.get("action")
    with LOCK:
        rows_store = rows_for_client(client_id)
        jobs_store = jobs_for_client(client_id)
        if action == "toggle":
            row_id = payload.get("row_id")
            if row_id not in rows_store:
                return jsonify({"error": "账号不存在"}), 404
            rows_store[row_id].selected = bool(payload.get("selected"))
            rows_store[row_id].updated_at = now_iso()
        elif action == "select_all":
            selected = bool(payload.get("selected"))
            for row in rows_store.values():
                row.selected = selected
                row.updated_at = now_iso()
        elif action == "delete_selected":
            requested_ids = payload.get("row_ids") or []
            if requested_ids:
                remove_ids = [
                    str(row_id)
                    for row_id in requested_ids
                    if str(row_id) in rows_store and rows_store[str(row_id)].status != "running"
                ]
            else:
                remove_ids = [row_id for row_id, row in rows_store.items() if row.selected and row.status != "running"]
            for row_id in remove_ids:
                rows_store.pop(row_id, None)
            keep_jobs = {job_id: job for job_id, job in jobs_store.items() if job.row_id in rows_store}
            jobs_store.clear()
            jobs_store.update(keep_jobs)
        else:
            return jsonify({"error": "不支持的操作"}), 400
    return jsonify_snapshot(client_id, ok=True)


@app.post("/api/otp")
def read_otp():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
    except Exception as exc:
        return api_error_response(exc)
    row_id = payload.get("row_id")
    if not row_id:
        return jsonify({"error": "缺少 row_id"}), 400
    with LOCK:
        row = rows_for_client(client_id).get(row_id)
        if not row:
            return jsonify({"error": "账号不存在"}), 404
        account = OutlookAccount(
            email=row.email,
            password=row.password,
            client_id=row.client_id,
            refresh_token=row.refresh_token,
        )
    try:
        otp = fetch_otp_with_account(
            account,
            after_ts=time.time() - 120,
            max_wait=8,
            poll_interval=2,
            settle_seconds=0,
        )
    except Exception as exc:
        return jsonify({"error": otp_read_failure_reason(account, exc, max_age_seconds=120)}), 400
    update_row(client_id, row_id, otp=otp)
    return jsonify_snapshot(client_id, email=account.email, otp=otp)


@app.post("/api/run")
def run_accounts():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
    except Exception as exc:
        return api_error_response(exc)
    row_ids = payload.get("row_ids") or []
    output_format = normalize_output_format(payload.get("format"))
    concurrency = int(payload.get("concurrency") or DEFAULT_CONCURRENCY)
    concurrency = max(1, min(MAX_CONCURRENCY, concurrency))

    if output_format not in (*FORMATS, "all"):
        return jsonify({"error": "不支持的导出格式"}), 400

    with LOCK:
        rows_store = rows_for_client(client_id)
        jobs_store = jobs_for_client(client_id)
        rows = [rows_store[row_id] for row_id in row_ids if row_id in rows_store and rows_store[row_id].status != "running"]
        if not rows:
            return jsonify({"error": "没有可运行的账号"}), 400

        jobs: list[Job] = []
        for row in rows:
            job = Job(
                id=secrets.token_urlsafe(8),
                client_id=client_id,
                row_id=row.id,
                email=row.email,
                format=output_format,
            )
            jobs_store[job.id] = job
            row.status = "running"
            row.error = ""
            row.running_job_id = job.id
            row.updated_at = now_iso()
            jobs.append(job)

    def worker(run_job: Job) -> None:
        run_account_job(run_job)

    threading.Thread(
        target=lambda: ThreadPoolExecutor(max_workers=concurrency).map(worker, jobs),
        daemon=True,
    ).start()
    return jsonify_snapshot(client_id, started=len(jobs), concurrency=concurrency)


@app.post("/api/export")
def export_accounts():
    payload = get_request_payload()
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
    except Exception as exc:
        return api_error_response(exc)
    row_ids = payload.get("row_ids") or []
    output_format = normalize_output_format(payload.get("format"))
    if output_format not in (*FORMATS, "all"):
        return jsonify({"error": "不支持的导出格式"}), 400
    with LOCK:
        rows_store = rows_for_client(client_id)
        rows = [rows_store[row_id] for row_id in row_ids if row_id in rows_store]
    if not rows:
        return jsonify({"error": "请先勾选要导出的账号"}), 400

    missing = [row.email for row in rows if not row.session_info]
    if missing:
        return jsonify({
            "error": "以下账号尚未就绪，请重新取号或联系管理员: " + ", ".join(missing[:5]),
        }), 400

    try:
        files = build_export_files(rows, output_format)
    except Exception as exc:
        log_exception(
            category="export",
            action="client.export",
            message="前台导出失败",
            exc=exc,
            client_id=client_id,
            detail={"format": output_format, "rowCount": len(rows)},
        )
        return api_error_response(exc)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if output_format == "all" or len(files) > 1:
        filename = f"{output_format}-export-{stamp}.zip"
        content = build_zip_bytes(files)
        mime_type = "application/zip"
    else:
        filename, document = files[0]
        content = json.dumps(document, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        mime_type = "application/json"

    with LOCK:
        for row in rows:
            row.exported_formats = [output_format] if output_format != "all" else list(FORMATS)
            row.files = []
            row.updated_at = now_iso()

    response = snapshot_payload(
        client_id,
        filename=filename,
        mimeType=mime_type,
        contentBase64=base64.b64encode(content).decode("ascii"),
    )
    log_activity(
        category="export",
        action="client.export",
        message=f"前台导出 {output_format} x{len(rows)} -> {filename}",
        client_id=client_id,
        status="success",
        detail={
            "format": output_format,
            "rowCount": len(rows),
            "filename": filename,
            "mimeType": mime_type,
            "emails": [row.email for row in rows[:20]],
        },
    )
    clear_client_cache_after_response(client_id)
    return jsonify(response)


@app.post("/api/redeem")
def redeem_card_key():
    payload = get_request_payload()
    client_id = ""
    card_key = ""
    try:
        client_id = get_client_id(payload)
        sync_client_rows(client_id, payload)
        card_key = str(payload.get("card_key") or payload.get("cardKey") or "").strip()
        if not is_valid_card_code(card_key):
            raise ValueError("卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位")
        account = redeem_card(card_key)
    except Exception as exc:
        log_exception(
            category="redeem",
            action="client.redeem",
            message="前台取号失败",
            exc=exc,
            client_id=client_id,
            card_code=card_key,
        )
        return api_error_response(exc)

    log_activity(
        category="redeem",
        action="client.redeem",
        message=f"前台取号成功 -> {account['email']}",
        account_id=account["id"],
        email=account["email"],
        card_code=account.get("cardCode") or card_key,
        client_id=client_id,
        status="success",
        detail={"reused": account.get("reused", False)},
    )

    with LOCK:
        upsert_redeemed_row(client_id, account)

    return jsonify_snapshot(
        client_id,
        email=account["email"],
        accountId=account["id"],
        cardCode=account["cardCode"],
        reused=account.get("reused", False),
    )


@app.get("/admin")
def admin_page():
    return Response(
        ADMIN_HTML,
        mimetype="text/html; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "X-Build-Id": str(ADMIN_BUILD_ID),
        },
    )


@app.get("/api/admin/health")
def admin_health():
    return jsonify(
        {
            "ok": True,
            "buildId": ADMIN_BUILD_ID,
            "version": align_runtime_version(),
            "features": list(SERVER_FEATURES),
            "dbPath": str(get_database_path()),
        }
    )


@app.post("/api/admin/login")
def admin_login():
    payload = get_request_payload()
    password = str(payload.get("password") or "")
    if not verify_admin_password(password):
        log_activity(
            level="warn",
            category="admin",
            action="admin.login",
            message="后台登录失败：密码错误",
            status="failed",
            detail={"ip": request.remote_addr, "userAgent": request.headers.get("User-Agent", "")},
        )
        return jsonify({"error": "管理员密码错误"}), 401
    token = issue_admin_token()
    log_activity(
        category="admin",
        action="admin.login",
        message="后台登录成功",
        status="success",
        detail={"ip": request.remote_addr, "userAgent": request.headers.get("User-Agent", "")},
    )
    return jsonify({"token": token, "expiresIn": ADMIN_TOKEN_TTL_SECONDS})


@app.get("/api/admin/dashboard")
def admin_dashboard():
    denied = admin_required()
    if denied:
        return denied
    return jsonify({"stats": get_stats(), "buildId": ADMIN_BUILD_ID, "version": align_runtime_version()})


@app.get("/api/admin/version")
def admin_version():
    denied = admin_required()
    if denied:
        return denied
    check = request.args.get("check", "").strip().lower() in {"1", "true", "yes"}
    payload = build_version_payload(include_remote=check)
    payload["databasePath"] = str(get_database_path())
    payload["backups"] = list_database_backups(limit=5)
    return jsonify(payload)


@app.post("/api/admin/database/backup")
def admin_database_backup():
    denied = admin_required()
    if denied:
        return denied
    try:
        path = create_database_backup()
        log_activity(
            category="admin",
            action="database.backup",
            message=f"数据库已备份: {path.name}",
            status="success",
        )
        return jsonify({"ok": True, "path": str(path), "backups": list_database_backups()})
    except Exception as exc:
        return api_error_response(exc)


@app.get("/api/admin/database/download")
def admin_database_download():
    denied = admin_required()
    if denied:
        return denied
    db_path = get_database_path()
    if not db_path.is_file():
        return jsonify({"ok": False, "error": "数据库文件不存在"}), 404
    return send_file(
        db_path,
        mimetype="application/octet-stream",
        as_attachment=True,
        download_name=f"codex-backup-{db_path.name}",
    )


@app.post("/api/admin/update/run")
def admin_update_run():
    denied = admin_required()
    if denied:
        return denied
    meta = build_version_payload(include_remote=False)
    if not meta.get("selfUpdateEnabled"):
        return jsonify({"ok": False, "error": "未启用 ENABLE_SELF_UPDATE，请在环境变量中设置"}), 403
    readiness = meta.get("updateReadiness") or {}
    if not readiness.get("ready"):
        issues = readiness.get("issues") or []
        return jsonify({"ok": False, "error": "；".join(issues) or "环境未就绪"}), 400
    log_activity(
        category="admin",
        action="update.start",
        message="开始执行一键更新（后台任务）",
        status="running",
        detail={"script": str(meta.get("updateScript") or "")},
    )
    result = start_update_job()
    if not result.get("ok"):
        return jsonify(result), 400
    return jsonify(result)


@app.get("/api/admin/update/status")
def admin_update_status():
    denied = admin_required()
    if denied:
        return denied
    return jsonify(get_update_status())


@app.get("/api/admin/update/diag")
def admin_update_diag():
    denied = admin_required()
    if denied:
        return denied
    from core.app_version import get_docker_bind_path, get_host_install_dir
    from core.update_job import LOG_FILE, _job_running, _read_log_tail

    bind = get_docker_bind_path()
    log = _read_log_tail()
    return jsonify(
        {
            "hostInstallDir": get_host_install_dir(),
            "hostBindPath": bind,
            "hostBindPathOk": bind not in {"", "/host-codex", "/app"},
            "jobRunning": _job_running(),
            "logPath": str(LOG_FILE),
            "log": log,
            "triggerScript": str(
                Path("/host-codex/scripts/trigger-update.py")
                if Path("/host-codex/scripts/trigger-update.py").is_file()
                else Path(__file__).resolve().parent.parent / "scripts" / "trigger-update.py"
            ),
        }
    )


@app.get("/api/admin/cards")
def admin_list_cards():
    denied = admin_required()
    if denied:
        return denied
    try:
        page = request.args.get("page", 1)
        page_size = request.args.get("pageSize", 10)
        pool_type = request.args.get("poolType") or request.args.get("pool_type")
        data = list_cards_page(page, page_size, pool_type=pool_type)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.get("/api/admin/logs")
def admin_list_logs():
    denied = admin_required()
    if denied:
        return denied
    try:
        data = list_activity_logs(
            page=request.args.get("page", 1),
            page_size=request.args.get("pageSize", 100),
            category=request.args.get("category") or None,
            level=request.args.get("level") or None,
            email=request.args.get("email") or None,
            action=request.args.get("action") or None,
        )
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/logs/clear")
def admin_clear_logs():
    denied = admin_required()
    if denied:
        return denied
    try:
        deleted = clear_all_activity_logs()
    except Exception as exc:
        log_exception(category="admin", action="logs.clear", message="清空日志失败", exc=exc)
        return api_error_response(exc)
    return jsonify({"ok": True, "deleted": deleted})


@app.get("/api/admin/accounts")
def admin_list_accounts():
    denied = admin_required()
    if denied:
        return denied
    try:
        page = request.args.get("page", 1)
        page_size = request.args.get("pageSize", 10)
        group = request.args.get("group")
        pool_type = request.args.get("poolType") or request.args.get("pool_type")
        data = list_accounts_page(page, page_size, group=group, pool_type=pool_type)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/cards/delete")
def admin_delete_card():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        delete_card_key(str(payload.get("code") or "").strip())
    except Exception as exc:
        return api_error_response(exc)
    return jsonify({"ok": True, "stats": get_stats()})


@app.post("/api/admin/proxy/test")
def admin_test_proxy_pool():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        proxy_pool_text = payload.get("proxyPoolText")
        if proxy_pool_text is None:
            from core.app_settings import get_proxy_pool

            data = test_proxy_pool(proxies=get_proxy_pool())
        else:
            data = test_proxy_pool(proxy_pool_text=str(proxy_pool_text))
    except Exception as exc:
        log_exception(category="settings", action="proxy.test", message="代理池测试失败", exc=exc)
        return api_error_response(exc)
    log_activity(
        category="settings",
        action="proxy.test",
        message=data.get("summary") or "代理池测试完成",
        status="success" if (data.get("failed") or 0) == 0 else "failed",
        detail=data,
    )
    return jsonify(data)


@app.post("/api/admin/auto-test/run")
def admin_run_auto_test_now():
    denied = admin_required()
    if denied:
        return denied
    result = request_auto_test_now()
    if result.get("ok"):
        log_activity(
            category="test",
            action="auto_test.manual",
            message=result.get("message") or "手动触发立即测试",
            status="running",
            detail={"total": result.get("total")},
        )
        return jsonify(result)
    if result.get("skipped"):
        return jsonify(result), 409
    return jsonify(result), 400


@app.get("/api/admin/settings")
def admin_get_settings():
    denied = admin_required()
    if denied:
        return denied
    base_url = resolve_public_base_url(request)
    return jsonify({**get_public_settings(), **get_public_api_gateway_settings(base_url=base_url, request=request)})


@app.post("/api/admin/settings/reset-api-key")
def admin_reset_api_key():
    denied = admin_required()
    if denied:
        return denied
    key = reset_api_gateway_key()
    base_url = resolve_public_base_url(request)
    log_activity(
        category="settings",
        action="settings.reset_api_key",
        message="API 网关密钥已重置",
        status="success",
    )
    return jsonify(
        {
            **get_public_api_gateway_settings(base_url=base_url, request=request),
            "apiGatewayKey": key,
        }
    )


@app.post("/api/admin/settings")
def admin_save_settings():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        new_password = payload.get("newPassword")
        confirm_password = payload.get("confirmPassword")
        clear_password = bool(payload.get("clearPassword"))
        proxy_pool_text = payload.get("proxyPoolText")

        if new_password not in (None, ""):
            if str(new_password) != str(confirm_password or ""):
                raise ValueError("两次输入的登录密码不一致")
        elif confirm_password:
            raise ValueError("请填写新登录密码")

        kwargs: dict[str, Any] = {}
        if clear_password:
            kwargs["clear_password"] = True
        elif new_password not in (None, ""):
            kwargs["new_password"] = str(new_password)
        if proxy_pool_text is not None:
            kwargs["proxy_pool_text"] = str(proxy_pool_text)
        if payload.get("testModelsText") is not None:
            kwargs["test_models_text"] = str(payload.get("testModelsText"))
        if payload.get("defaultTestModel") is not None:
            kwargs["default_test_model"] = str(payload.get("defaultTestModel"))
        if payload.get("defaultTestMessage") is not None:
            kwargs["default_test_message"] = str(payload.get("defaultTestMessage"))
        if payload.get("autoTestIntervalHours") is not None or payload.get("auto_test_interval_hours") is not None:
            kwargs["auto_test_interval_hours"] = int(
                payload.get("autoTestIntervalHours", payload.get("auto_test_interval_hours", 0))
            )
        if payload.get("publicBaseUrl") is not None or payload.get("public_base_url") is not None:
            kwargs["public_base_url"] = str(payload.get("publicBaseUrl", payload.get("public_base_url", "")))
        data = update_settings(**kwargs)
    except Exception as exc:
        log_exception(category="settings", action="settings.save", message="保存设置失败", exc=exc)
        return api_error_response(exc)
    log_activity(
        category="settings",
        action="settings.save",
        message="后台设置已保存",
        status="success",
        detail={
            "passwordChanged": new_password not in (None, ""),
            "passwordReset": clear_password,
            "proxyPoolUpdated": proxy_pool_text is not None,
            "testModelsUpdated": payload.get("testModelsText") is not None,
            "proxyCount": data.get("proxyCount"),
            "modelCount": len(data.get("models") or []),
        },
    )
    return jsonify({"ok": True, "settings": data})


@app.post("/api/admin/accounts/import")
def admin_import_accounts():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        if str(payload.get("action") or "").strip().lower() == "delete":
            account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
            if not account_id:
                raise ValueError("缺少 accountId")
            delete_pool_account(account_id)
            return jsonify({"ok": True, "stats": get_stats()})

        account_type = str(payload.get("accountType") or payload.get("type") or "email")
        import_kwargs = {
            "material": payload.get("material") or "",
            "account_type": account_type,
            "oauth_method": str(payload.get("oauthMethod") or payload.get("oauth_method") or "codex_json"),
            "session_id": str(payload.get("sessionId") or payload.get("session_id") or ""),
            "auth_input": str(payload.get("authInput") or payload.get("auth_input") or ""),
            "state": str(payload.get("state") or ""),
            "pool_type": str(payload.get("poolType") or payload.get("pool_type") or "pp"),
            "remark": str(payload.get("remark") or ""),
        }
        stream = bool(payload.get("stream"))
        background = payload.get("background", True)
        material = str(import_kwargs.get("material") or "")
        log_activity(
            category="import",
            action="import.request",
            message=f"后台发起导入 ({account_type})",
            status="running",
            detail={
                "accountType": account_type,
                "oauthMethod": import_kwargs.get("oauth_method"),
                "stream": stream,
                "background": background,
                "materialLines": len([line for line in material.splitlines() if line.strip()]),
                "materialChars": len(material),
            },
        )
        if stream:
            @stream_with_context
            def generate():
                try:
                    for event in iter_import_pool_accounts(**import_kwargs):
                        yield json.dumps(event, ensure_ascii=False) + "\n"
                    stats = get_stats()
                    yield json.dumps({"type": "stats", "stats": stats}, ensure_ascii=False) + "\n"
                except Exception as exc:
                    yield json.dumps({"type": "error", "error": public_error_message(exc)}, ensure_ascii=False) + "\n"

            return Response(generate(), mimetype="application/x-ndjson")

        if background:
            result = import_pool_accounts_background(**import_kwargs)
        else:
            result = import_pool_accounts(**import_kwargs)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify({**result, "stats": get_stats()})


@app.post("/api/admin/accounts/priority-sale")
def admin_set_account_priority_sale():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        enabled = payload.get("enabled")
        if enabled is None:
            enabled = payload.get("prioritySale")
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        else:
            enabled = bool(enabled)
        result = set_pool_account_priority_sale(account_id, enabled=enabled)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(result)


@app.post("/api/admin/accounts/remark")
def admin_update_account_remark():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        remark = str(payload.get("remark") or "")
        result = update_pool_account_remark(account_id, remark)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(result)


@app.post("/api/admin/accounts/mailbox-link")
def admin_link_mailbox():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        material = str(payload.get("material") or payload.get("mailboxMaterial") or "").strip()
        result = link_mailbox_to_oauth_account(account_id, material)
    except Exception as exc:
        log_exception(category="settings", action="account.mailbox_link", message="绑定邮箱失败", exc=exc)
        return api_error_response(exc)
    return jsonify(result)


@app.post("/api/admin/accounts/oauth-link")
def admin_link_optional_oauth():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        result = link_optional_oauth_pool_account(
            account_id,
            oauth_method=str(payload.get("oauthMethod") or payload.get("oauth_method") or "manual"),
            session_id=str(payload.get("sessionId") or payload.get("session_id") or ""),
            auth_input=str(payload.get("authInput") or payload.get("auth_input") or ""),
            state=str(payload.get("state") or ""),
            material=str(payload.get("material") or ""),
        )
    except Exception as exc:
        log_exception(category="oauth", action="oauth.link_optional", message="可选 OAuth 绑定失败", exc=exc)
        return api_error_response(exc)
    return jsonify({**result, "stats": get_stats()})


@app.post("/api/admin/accounts/reauthorize")
def admin_reauthorize_account():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        result = reauthorize_pool_account(
            account_id,
            oauth_method=str(payload.get("oauthMethod") or payload.get("oauth_method") or "manual"),
            session_id=str(payload.get("sessionId") or payload.get("session_id") or ""),
            auth_input=str(payload.get("authInput") or payload.get("auth_input") or ""),
            state=str(payload.get("state") or ""),
            material=str(payload.get("material") or ""),
        )
    except Exception as exc:
        return api_error_response(exc)
    return jsonify({**result, "stats": get_stats()})


@app.post("/api/admin/openai/generate-auth-url")
def admin_openai_generate_auth_url():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        data = generate_auth_url(redirect_uri=str(payload.get("redirectUri") or payload.get("redirect_uri") or ""))
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/accounts/delete")
def admin_delete_account():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        delete_pool_account(account_id)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify({"ok": True, "stats": get_stats()})


@app.post("/api/admin/accounts/otp")
def admin_read_account_otp():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        data = read_pool_account_otp(account_id)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/accounts/quota")
def admin_query_account_quota():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        data = query_pool_account_quota(account_id)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.get("/api/admin/accounts/test-options")
def admin_account_test_options():
    denied = admin_required()
    if denied:
        return denied
    return jsonify(get_test_settings())


@app.post("/api/admin/accounts/proxy")
def admin_update_account_proxy():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        data = update_pool_account_proxy(account_id, payload.get("proxy"))
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/accounts/export")
def admin_export_account():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        output_format = str(payload.get("format") or "sub2api").strip().lower()
        data = export_pool_account(account_id, output_format)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/accounts/test")
def admin_test_account():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        account_id = str(payload.get("accountId") or payload.get("id") or "").strip()
        if not account_id:
            raise ValueError("缺少 accountId")
        data = test_pool_account(
            account_id,
            model=str(payload.get("model") or DEFAULT_TEST_MODEL),
            message=str(payload.get("message") or DEFAULT_TEST_MESSAGE),
        )
    except Exception as exc:
        return api_error_response(exc)
    return jsonify(data)


@app.post("/api/admin/cards/create")
def admin_create_cards():
    denied = admin_required()
    if denied:
        return denied
    payload = get_request_payload()
    try:
        count = int(payload.get("count") or 1)
        pool_type = str(payload.get("poolType") or payload.get("pool_type") or "pp")
        codes = create_card_keys(count, pool_type=pool_type)
    except Exception as exc:
        return api_error_response(exc)
    return jsonify({"count": len(codes), "codes": codes, "poolType": pool_type, "stats": get_stats(pool_type=pool_type)})


def main() -> int:
    import argparse

    init_db()
    apply_runtime_settings()
    from core.api_gateway import get_api_gateway_key

    get_api_gateway_key()
    start_auto_test_scheduler()
    log_activity(
        category="system",
        action="server.start",
        message="后台服务已启动",
        status="success",
        detail={"buildId": ADMIN_BUILD_ID, "features": list(SERVER_FEATURES)},
    )
    _register_api_error_handlers(app)
    _register_gateway_routes(app)
    parser = argparse.ArgumentParser(description="启动批量 Session 导出控制台")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    print(f"打开 http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

_register_api_error_handlers(app)
_register_gateway_routes(app)
