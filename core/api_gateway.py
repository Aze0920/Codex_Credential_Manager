# -*- coding: utf-8 -*-
"""对外 API 网关：可重置密钥，多上游 OpenAI 兼容接口。"""
from __future__ import annotations

import re
import secrets
from typing import Any

from core.card_store import (
    _account_counts_as_failed,
    _parse_quota_data,
    _resolve_pool_account_credentials,
    _connect,
    get_setting,
    init_db,
    set_setting,
    LOCK,
)

API_KEY_SETTING = "api_gateway_key"
PUBLIC_BASE_URL_SETTING = "public_base_url"

PROVIDER_PROFILES: tuple[dict[str, str], ...] = (
    {
        "id": "openai",
        "name": "OpenAI 官方",
        "routePrefix": "/v1",
        "upstreamBase": "https://api.openai.com/v1",
        "authMode": "pool",
        "note": "标准 OpenAI 兼容接口，如 /v1/chat/completions、/v1/models",
    },
    {
        "id": "codex",
        "name": "ChatGPT Codex",
        "routePrefix": "/codex/v1",
        "upstreamBase": "https://chatgpt.com/backend-api/codex",
        "authMode": "pool",
        "note": "账号池 OAuth/邮箱登录凭证，适合 Codex 模型测试与调用",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "routePrefix": "/openrouter/v1",
        "upstreamBase": "https://openrouter.ai/api/v1",
        "authMode": "pool",
        "note": "OpenRouter 聚合接口，路径与 OpenAI 兼容",
    },
    {
        "id": "groq",
        "name": "Groq",
        "routePrefix": "/groq/v1",
        "upstreamBase": "https://api.groq.com/openai/v1",
        "authMode": "pool",
        "note": "Groq OpenAI 兼容接口",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "routePrefix": "/deepseek/v1",
        "upstreamBase": "https://api.deepseek.com/v1",
        "authMode": "pool",
        "note": "DeepSeek OpenAI 兼容接口",
    },
    {
        "id": "moonshot",
        "name": "Moonshot",
        "routePrefix": "/moonshot/v1",
        "upstreamBase": "https://api.moonshot.cn/v1",
        "authMode": "pool",
        "note": "月之暗面 Kimi OpenAI 兼容接口",
    },
    {
        "id": "siliconflow",
        "name": "SiliconFlow",
        "routePrefix": "/siliconflow/v1",
        "upstreamBase": "https://api.siliconflow.cn/v1",
        "authMode": "pool",
        "note": "硅基流动 OpenAI 兼容接口",
    },
    {
        "id": "cloudflare",
        "name": "Cloudflare AI",
        "routePrefix": "/cloudflare/v1",
        "upstreamBase": "https://api.cloudflare.com/client/v4/accounts",
        "authMode": "pool",
        "note": "Cloudflare Workers AI（部分路径需自行拼接 account/model）",
    },
)

_ROUTE_BY_PREFIX: dict[str, dict[str, str]] = {
    profile["routePrefix"].rstrip("/"): profile for profile in PROVIDER_PROFILES
}


def ensure_api_gateway_ready() -> None:
    init_db()


def get_api_gateway_key() -> str:
    ensure_api_gateway_ready()
    key = (get_setting(API_KEY_SETTING) or "").strip()
    if key:
        return key
    return reset_api_gateway_key()


def reset_api_gateway_key() -> str:
    ensure_api_gateway_ready()
    key = secrets.token_urlsafe(32)
    set_setting(API_KEY_SETTING, key)
    return key


def mask_api_gateway_key(key: str) -> str:
    text = (key or "").strip()
    if len(text) <= 10:
        return "*" * len(text)
    return f"{text[:6]}...{text[-4:]}"


def verify_api_gateway_key(candidate: str | None) -> bool:
    expected = (get_api_gateway_key() or "").strip()
    provided = (candidate or "").strip()
    if not expected or not provided:
        return False
    return secrets.compare_digest(expected, provided)


def extract_bearer_token(authorization: str | None) -> str:
    auth = (authorization or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def normalize_public_base_url(value: str | None) -> str:
    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    if not re.match(r"^https?://", text, re.I):
        text = f"https://{text}"
    return text.rstrip("/")


def get_configured_public_base_url() -> str:
    ensure_api_gateway_ready()
    return normalize_public_base_url(get_setting(PUBLIC_BASE_URL_SETTING) or "")


def set_configured_public_base_url(value: str | None) -> str:
    ensure_api_gateway_ready()
    normalized = normalize_public_base_url(value)
    if normalized:
        set_setting(PUBLIC_BASE_URL_SETTING, normalized)
    else:
        from core.card_store import delete_setting

        delete_setting(PUBLIC_BASE_URL_SETTING)
    return normalized


def resolve_public_base_url(request: Any | None = None) -> str:
    configured = get_configured_public_base_url()
    if configured:
        return configured
    if request is None:
        return ""
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    forwarded_host = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip()
    if forwarded_host:
        scheme = forwarded_proto or getattr(request, "scheme", None) or "http"
        return f"{scheme}://{forwarded_host}".rstrip("/")
    return (getattr(request, "url_root", None) or "").rstrip("/")


def get_public_api_gateway_settings(*, base_url: str, request: Any | None = None) -> dict[str, Any]:
    key = get_api_gateway_key()
    base = (base_url or "").rstrip("/")
    providers = []
    for profile in PROVIDER_PROFILES:
        prefix = profile["routePrefix"].rstrip("/")
        providers.append(
            {
                **profile,
                "exampleUrl": f"{base}{prefix}/chat/completions",
                "modelsUrl": f"{base}{prefix}/models",
            }
        )
    return {
        "apiGatewayKey": key,
        "apiGatewayKeyMasked": mask_api_gateway_key(key),
        "apiGatewayBaseUrl": base,
        "publicBaseUrl": get_configured_public_base_url(),
        "apiGatewayBaseUrlAuto": resolve_public_base_url(request) if not get_configured_public_base_url() else "",
        "apiProviders": providers,
    }


def match_provider(path: str) -> tuple[dict[str, str] | None, str]:
    normalized = "/" + str(path or "").lstrip("/")
    best: dict[str, str] | None = None
    best_prefix = ""
    for prefix, profile in sorted(_ROUTE_BY_PREFIX.items(), key=lambda item: len(item[0]), reverse=True):
        if normalized == prefix or normalized.startswith(prefix + "/"):
            best = profile
            best_prefix = prefix
            break
    if not best:
        return None, normalized.lstrip("/")
    subpath = normalized[len(best_prefix) :].lstrip("/")
    return best, subpath


def _pick_gateway_account_row():
    with LOCK:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, email, password, client_id, refresh_token, material,
                       account_type, oauth_data, status, test_status, test_result, last_test_at,
                       quota_data, quota_updated_at, assigned_proxy, mailbox_material, pool_type
                FROM pool_accounts
                WHERE status = 'available'
                  AND test_status = 'success'
                ORDER BY last_test_at DESC, created_at ASC
                """
            ).fetchall()
        finally:
            conn.close()
    for row in rows:
        if _account_counts_as_failed(row["test_status"], row["quota_data"]):
            continue
        quota = _parse_quota_data(row["quota_data"])
        if isinstance(quota, dict) and quota.get("ok") is False:
            continue
        return row
    return None


def pick_gateway_credentials() -> dict[str, Any]:
    row = _pick_gateway_account_row()
    if row is None:
        raise ValueError("暂无可用且测试通过的账号，无法转发 API 请求")
    credentials = _resolve_pool_account_credentials(row)
    return {
        "accountId": row["id"],
        "email": row["email"],
        "accessToken": credentials["accessToken"],
        "chatgptAccountId": credentials.get("chatgptAccountId") or "",
        "proxy": credentials.get("proxy") or "",
    }


def build_upstream_headers(
    profile: dict[str, str],
    credentials: dict[str, Any],
    incoming_headers: dict[str, str],
) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {credentials['accessToken']}",
        "Content-Type": incoming_headers.get("Content-Type") or incoming_headers.get("content-type") or "application/json",
        "Accept": incoming_headers.get("Accept") or incoming_headers.get("accept") or "application/json",
    }
    if profile["id"] in {"openai", "codex", "openrouter", "groq", "deepseek", "moonshot", "siliconflow"}:
        account_id = str(credentials.get("chatgptAccountId") or "").strip()
        if account_id and profile["id"] in {"codex", "openai"}:
            headers["chatgpt-account-id"] = account_id
    if profile["id"] == "codex":
        headers["Host"] = "chatgpt.com"
        headers["accept"] = incoming_headers.get("Accept") or incoming_headers.get("accept") or "text/event-stream"
    return headers


def forward_gateway_request(
    *,
    method: str,
    path: str,
    query_string: bytes,
    headers: dict[str, str],
    body: bytes,
    timeout: int = 120,
) -> tuple[int, dict[str, str], bytes]:
    from curl_cffi.requests import Session

    from config import IMPERSONATE, REQUEST_TIMEOUT, pick_proxy

    profile, subpath = match_provider(path)
    if not profile:
        raise ValueError(f"未知的 API 路由: {path}")

    credentials = pick_gateway_credentials()
    upstream = profile["upstreamBase"].rstrip("/")
    if subpath:
        upstream = f"{upstream}/{subpath.lstrip('/')}"
    if query_string:
        upstream = f"{upstream}?{query_string.decode('utf-8', errors='ignore')}"

    upstream_headers = build_upstream_headers(profile, credentials, headers)
    chosen_proxy = credentials.get("proxy") or pick_proxy()
    session = Session(impersonate=IMPERSONATE, timeout=min(timeout, REQUEST_TIMEOUT))
    if chosen_proxy:
        session.proxies = {"http": chosen_proxy, "https": chosen_proxy}

    response = session.request(
        method.upper(),
        upstream,
        headers=upstream_headers,
        data=body or None,
        timeout=timeout,
    )
    passthrough = {}
    content_type = response.headers.get("Content-Type")
    if content_type:
        passthrough["Content-Type"] = content_type
    return response.status_code, passthrough, response.content
