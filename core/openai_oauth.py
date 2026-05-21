# -*- coding: utf-8 -*-
"""OpenAI / ChatGPT OAuth（参考 sub2api Codex CLI 流程）。"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from curl_cffi.requests import Session

from config import IMPERSONATE, REQUEST_TIMEOUT, pick_proxy

CODEX_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
MOBILE_CLIENT_ID = "app_LlGpXReQgckcGGUo2JrYvtJK"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback"
DEFAULT_SCOPE = "openid profile email offline_access"
REFRESH_SCOPE = "openid profile email"
SESSION_TTL_SECONDS = 30 * 60
JWT_AUTH_CLAIM = "https://api.openai.com/auth"

_LOCK = threading.RLock()
_SESSIONS: dict[str, dict[str, Any]] = {}


@dataclass
class TokenInfo:
    access_token: str
    refresh_token: str = ""
    id_token: str = ""
    expires_in: int = 0
    expires_at: int = 0
    client_id: str = CODEX_CLIENT_ID
    email: str = ""
    chatgpt_account_id: str = ""
    chatgpt_user_id: str = ""
    organization_id: str = ""
    plan_type: str = ""


def _now_ts() -> int:
    return int(time.time())


def _cleanup_sessions() -> None:
    cutoff = _now_ts() - SESSION_TTL_SECONDS
    expired = [key for key, item in _SESSIONS.items() if int(item.get("created_at") or 0) < cutoff]
    for key in expired:
        _SESSIONS.pop(key, None)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _generate_code_verifier() -> str:
    return secrets.token_hex(64)


def _generate_code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return _b64url(digest)


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    parts = (token or "").split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def access_token_is_valid(token: str, *, margin_seconds: int = 120) -> bool:
    """判断 access_token 是否仍在有效期内。"""
    access_token = (token or "").strip()
    if not access_token:
        return False
    exp = _jwt_exp(access_token)
    if not exp:
        return True
    return exp > _now_ts() + margin_seconds


def _jwt_exp(token: str) -> int | None:
    payload = _decode_jwt_payload(token)
    exp = payload.get("exp")
    try:
        return int(exp)
    except (TypeError, ValueError):
        return None


def _extract_user_info(access_token: str, id_token: str = "") -> dict[str, str]:
    for token in (id_token, access_token):
        if not token:
            continue
        payload = _decode_jwt_payload(token)
        auth = payload.get(JWT_AUTH_CLAIM)
        if not isinstance(auth, dict):
            auth = {}
        email = str(payload.get("email") or auth.get("email") or "").strip()
        account_id = str(auth.get("chatgpt_account_id") or "").strip()
        user_id = str(auth.get("chatgpt_user_id") or auth.get("user_id") or payload.get("sub") or "").strip()
        plan_type = str(auth.get("chatgpt_plan_type") or "").strip()
        org_id = str(auth.get("poid") or "").strip()
        organizations = auth.get("organizations")
        if not org_id and isinstance(organizations, list):
            for org in organizations:
                if isinstance(org, dict) and org.get("is_default"):
                    org_id = str(org.get("id") or "").strip()
                    break
            if not org_id and organizations and isinstance(organizations[0], dict):
                org_id = str(organizations[0].get("id") or "").strip()
        if email or account_id or user_id:
            return {
                "email": email,
                "chatgpt_account_id": account_id,
                "chatgpt_user_id": user_id,
                "plan_type": plan_type,
                "organization_id": org_id,
            }
    return {}


def _http_session(proxy: str | None = None) -> Session:
    chosen = proxy if proxy is not None else pick_proxy()
    session = Session(impersonate=IMPERSONATE, timeout=REQUEST_TIMEOUT)
    if chosen:
        session.proxies = {"http": chosen, "https": chosen}
    return session


def generate_auth_url(*, redirect_uri: str | None = None) -> dict[str, str]:
    redirect = (redirect_uri or DEFAULT_REDIRECT_URI).strip()
    state = secrets.token_hex(32)
    verifier = _generate_code_verifier()
    challenge = _generate_code_challenge(verifier)
    session_id = secrets.token_hex(16)
    params = {
        "response_type": "code",
        "client_id": CODEX_CLIENT_ID,
        "redirect_uri": redirect,
        "scope": DEFAULT_SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
    }
    auth_url = f"{AUTHORIZE_URL}?{urlencode(params)}"
    with _LOCK:
        _cleanup_sessions()
        _SESSIONS[session_id] = {
            "state": state,
            "code_verifier": verifier,
            "redirect_uri": redirect,
            "client_id": CODEX_CLIENT_ID,
            "created_at": _now_ts(),
        }
    return {"authUrl": auth_url, "sessionId": session_id, "state": state, "redirectUri": redirect}


def parse_authorization_input(value: str) -> tuple[str, str]:
    text = (value or "").strip()
    if not text:
        raise ValueError("请输入授权回调链接或 code")
    code = ""
    state = ""
    if text.startswith("http://") or text.startswith("https://"):
        parsed = urlparse(text)
        query = parse_qs(parsed.query)
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [""])[0]
    elif "code=" in text:
        query = parse_qs(text)
        code = (query.get("code") or [""])[0]
        state = (query.get("state") or [""])[0]
    elif "#" in text and "code" not in text:
        code, state = text.split("#", 1)
    else:
        code = text
    code = (code or "").strip()
    state = (state or "").strip()
    if not code:
        raise ValueError("未解析到 authorization code")
    return code, state


def _token_response_to_info(data: dict[str, Any], *, client_id: str) -> TokenInfo:
    access_token = str(data.get("access_token") or "").strip()
    if not access_token:
        raise ValueError("令牌响应缺少 access_token")
    expires_in = int(data.get("expires_in") or 0)
    info = _extract_user_info(access_token, str(data.get("id_token") or ""))
    return TokenInfo(
        access_token=access_token,
        refresh_token=str(data.get("refresh_token") or "").strip(),
        id_token=str(data.get("id_token") or "").strip(),
        expires_in=expires_in,
        expires_at=_now_ts() + expires_in if expires_in else 0,
        client_id=client_id,
        email=info.get("email") or "",
        chatgpt_account_id=info.get("chatgpt_account_id") or "",
        chatgpt_user_id=info.get("chatgpt_user_id") or "",
        organization_id=info.get("organization_id") or "",
        plan_type=info.get("plan_type") or "",
    )


def exchange_authorization_code(
    *,
    session_id: str,
    code: str,
    state: str,
    redirect_uri: str | None = None,
    proxy: str | None = None,
) -> TokenInfo:
    with _LOCK:
        session = _SESSIONS.get(session_id)
    if not session:
        raise ValueError("授权会话不存在或已过期，请重新生成授权链接")
    if state and state != session.get("state"):
        raise ValueError("OAuth state 不匹配")
    redirect = (redirect_uri or session.get("redirect_uri") or DEFAULT_REDIRECT_URI).strip()
    body = urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": session.get("client_id") or CODEX_CLIENT_ID,
            "code": code.strip(),
            "redirect_uri": redirect,
            "code_verifier": session.get("code_verifier") or "",
        }
    )
    response = _http_session(proxy).post(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise ValueError(f"交换授权码失败: HTTP {response.status_code} {response.text[:300]}")
    token_info = _token_response_to_info(response.json(), client_id=str(session.get("client_id") or CODEX_CLIENT_ID))
    with _LOCK:
        _SESSIONS.pop(session_id, None)
    return token_info


def refresh_access_token(
    refresh_token: str,
    *,
    client_id: str | None = None,
    proxy: str | None = None,
) -> TokenInfo:
    rt = (refresh_token or "").strip()
    if not rt:
        raise ValueError("缺少 refresh_token")
    chosen_client = (client_id or CODEX_CLIENT_ID).strip()
    body = urlencode(
        {
            "grant_type": "refresh_token",
            "client_id": chosen_client,
            "refresh_token": rt,
            "scope": REFRESH_SCOPE,
        }
    )
    response = _http_session(proxy).post(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code != 200:
        raise ValueError(f"刷新令牌失败: HTTP {response.status_code} {response.text[:300]}")
    return _token_response_to_info(response.json(), client_id=chosen_client)


def ensure_fresh_oauth(oauth: dict[str, Any], *, proxy: str | None = None) -> dict[str, Any]:
    data = dict(oauth or {})
    access_token = str(data.get("access_token") or "").strip()
    refresh_token = str(data.get("refresh_token") or "").strip()
    client_id = str(data.get("client_id") or CODEX_CLIENT_ID).strip()
    exp = _jwt_exp(access_token) if access_token else None
    if access_token and exp and exp > _now_ts() + 120:
        return data
    if not refresh_token:
        if access_token:
            return data
        raise ValueError("access_token 已过期且缺少 refresh_token")
    token_info = refresh_access_token(refresh_token, client_id=client_id, proxy=proxy)
    data.update(token_info_to_oauth_data(token_info))
    return data


def token_info_to_oauth_data(token_info: TokenInfo) -> dict[str, Any]:
    expires_at = token_info.expires_at
    if expires_at:
        expires_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat()
    else:
        expires_iso = ""
    return {
        "access_token": token_info.access_token,
        "refresh_token": token_info.refresh_token,
        "id_token": token_info.id_token,
        "client_id": token_info.client_id,
        "email": token_info.email,
        "chatgpt_account_id": token_info.chatgpt_account_id,
        "chatgpt_user_id": token_info.chatgpt_user_id,
        "organization_id": token_info.organization_id,
        "plan_type": token_info.plan_type,
        "expires_at": expires_iso,
    }


def token_info_to_pool_record(token_info: TokenInfo) -> dict[str, str]:
    oauth_data = token_info_to_oauth_data(token_info)
    email = token_info.email or f"oauth-{token_info.chatgpt_account_id or secrets.token_hex(4)}"
    sub2api_account = {
        "name": email,
        "platform": "openai",
        "type": "oauth",
        "credentials": {
            "access_token": oauth_data["access_token"],
            "refresh_token": oauth_data.get("refresh_token") or "",
            "email": email,
            "chatgpt_account_id": oauth_data.get("chatgpt_account_id") or "",
            "chatgpt_user_id": oauth_data.get("chatgpt_user_id") or "",
            "plan_type": oauth_data.get("plan_type") or "",
            "client_id": oauth_data.get("client_id") or CODEX_CLIENT_ID,
            "expires_at": oauth_data.get("expires_at") or "",
        },
    }
    return {
        "account_type": "oauth",
        "email": email,
        "password": "",
        "client_id": oauth_data.get("client_id") or CODEX_CLIENT_ID,
        "refresh_token": oauth_data.get("refresh_token") or "",
        "material": json.dumps(sub2api_account, ensure_ascii=False),
        "oauth_data": json.dumps(oauth_data, ensure_ascii=False),
    }


def parse_codex_import_entries(content: str) -> list[dict[str, str]]:
    raw = (content or "").strip()
    if not raw:
        raise ValueError("请输入 Codex JSON 或 Access Token")

    records: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_token(access_token: str, refresh_token: str = "", account_id: str = "", email: str = "") -> None:
        token = (access_token or "").strip()
        if not token or token in seen:
            return
        seen.add(token)
        info = _extract_user_info(token)
        token_info = TokenInfo(
            access_token=token,
            refresh_token=(refresh_token or "").strip(),
            email=email or info.get("email") or "",
            chatgpt_account_id=account_id or info.get("chatgpt_account_id") or "",
            chatgpt_user_id=info.get("chatgpt_user_id") or "",
            plan_type=info.get("plan_type") or "",
        )
        records.append(token_info_to_pool_record(token_info))

    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSON 解析失败: {exc}") from exc
        items: list[Any]
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict) and isinstance(data.get("accounts"), list):
            items = data["accounts"]
        else:
            items = [data]
        for item in items:
            if not isinstance(item, dict):
                continue
            tokens = item.get("tokens") if isinstance(item.get("tokens"), dict) else {}
            credentials = item.get("credentials") if isinstance(item.get("credentials"), dict) else {}
            add_token(
                str(
                    tokens.get("access_token")
                    or tokens.get("accessToken")
                    or credentials.get("access_token")
                    or credentials.get("accessToken")
                    or item.get("access_token")
                    or item.get("accessToken")
                    or ""
                ),
                str(
                    tokens.get("refresh_token")
                    or tokens.get("refreshToken")
                    or credentials.get("refresh_token")
                    or credentials.get("refreshToken")
                    or item.get("refresh_token")
                    or item.get("refreshToken")
                    or ""
                ),
                str(
                    tokens.get("account_id")
                    or credentials.get("chatgpt_account_id")
                    or credentials.get("chatgptAccountId")
                    or item.get("chatgpt_account_id")
                    or ""
                ),
                str(item.get("email") or credentials.get("email") or item.get("name") or ""),
            )
        if records:
            return records

    for line in raw.splitlines():
        piece = line.strip()
        if not piece or piece.startswith("#"):
            continue
        if piece.startswith("{"):
            try:
                item = json.loads(piece)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                nested_records = parse_codex_import_entries(json.dumps(item, ensure_ascii=False))
                for record in nested_records:
                    material = record.get("material") or ""
                    if material not in seen:
                        seen.add(material)
                        records.append(record)
            continue
        if re.fullmatch(r"ey[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", piece):
            add_token(piece)
            continue
        if len(piece) > 40:
            add_token(piece)
    if not records:
        raise ValueError("没有解析到有效的 Codex JSON / Access Token")
    return records
