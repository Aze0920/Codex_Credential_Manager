# -*- coding: utf-8 -*-
"""测试 ChatGPT OAuth / Codex 账号连通性（参考 sub2api account test）。"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from curl_cffi.requests import Session

from config import IMPERSONATE, REQUEST_TIMEOUT, pick_proxy
from core.openai_oauth import _extract_user_info

CHATGPT_CODEX_API = "https://chatgpt.com/backend-api/codex/responses"
INSTRUCTIONS_PATH = Path(__file__).with_name("openai_instructions.txt")
DEFAULT_TEST_MODEL = "gpt-5.3-codex"
DEFAULT_TEST_MESSAGE = "hi"
TEST_MODELS = (
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
    "gpt-5.3-codex",
    "gpt-5.2",
)


def _allowed_test_models() -> tuple[str, ...]:
    try:
        from core.app_settings import get_allowed_test_models

        models = get_allowed_test_models()
        return models or TEST_MODELS
    except Exception:
        return TEST_MODELS

SSE_DATA_PREFIX = re.compile(r"^data:\s*")
_DEFAULT_INSTRUCTIONS: str | None = None


def _load_default_instructions() -> str:
    global _DEFAULT_INSTRUCTIONS
    if _DEFAULT_INSTRUCTIONS is not None:
        return _DEFAULT_INSTRUCTIONS
    try:
        text = INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    _DEFAULT_INSTRUCTIONS = text or "You are Codex, a helpful coding assistant."
    return _DEFAULT_INSTRUCTIONS


def normalize_test_model(value: str | None, *, allowed: tuple[str, ...] | None = None) -> str:
    model = (value or DEFAULT_TEST_MODEL).strip()
    allowed_models = allowed or TEST_MODELS
    if model not in allowed_models:
        allowed = "、".join(allowed_models)
        raise ValueError(f"不支持的模型，可选：{allowed}")
    return model


def build_test_payload(model: str, message: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": message or DEFAULT_TEST_MESSAGE}],
            }
        ],
        "stream": True,
        "store": False,
        "instructions": _load_default_instructions(),
    }


def _build_oauth_headers(access_token: str, account_id: str) -> dict[str, str]:
    """OAuth 测试请求头，与 sub2api testOpenAIAccountConnection 保持一致。"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Host": "chatgpt.com",
        "accept": "text/event-stream",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def _parse_sse_text(body_text: str, *, max_chars: int = 500) -> dict[str, Any]:
    chunks: list[str] = []
    seen_completed = False
    error_message = ""

    for raw_line in (body_text or "").splitlines():
        line = raw_line.strip()
        if not line or not SSE_DATA_PREFIX.match(line):
            continue

        payload_text = SSE_DATA_PREFIX.sub("", line)
        if payload_text == "[DONE]":
            seen_completed = True
            break

        try:
            event = json.loads(payload_text)
        except json.JSONDecodeError:
            continue

        event_type = str(event.get("type") or "")
        if event_type == "response.output_text.delta":
            delta = event.get("delta")
            if isinstance(delta, str) and delta:
                chunks.append(delta)
        elif event_type in {"response.completed", "response.done"}:
            seen_completed = True
            break
        elif event_type == "response.failed":
            response_data = event.get("response") if isinstance(event.get("response"), dict) else {}
            error_data = response_data.get("error") if isinstance(response_data.get("error"), dict) else {}
            error_message = str(error_data.get("message") or "OpenAI 响应失败")
            break
        elif event_type == "error":
            error_data = event.get("error") if isinstance(event.get("error"), dict) else {}
            error_message = str(error_data.get("message") or "未知错误")
            break

    reply = "".join(chunks).strip()
    if error_message:
        return {"ok": False, "reply": reply[:max_chars], "error": error_message}
    if seen_completed or reply:
        return {"ok": True, "reply": reply[:max_chars], "error": ""}
    return {"ok": False, "reply": "", "error": "流式响应未完成"}


def _resolve_account_id(access_token: str, chatgpt_account_id: str | None) -> str:
    account_id = (chatgpt_account_id or "").strip()
    if account_id:
        return account_id
    return _extract_user_info(access_token).get("chatgpt_account_id") or ""


def test_chatgpt_oauth(
    access_token: str,
    *,
    chatgpt_account_id: str | None = None,
    model: str | None = None,
    message: str | None = None,
    proxy: str | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise ValueError("缺少 access_token")

    test_model = normalize_test_model(model, allowed=_allowed_test_models())
    test_message = (message or DEFAULT_TEST_MESSAGE).strip() or DEFAULT_TEST_MESSAGE
    account_id = _resolve_account_id(token, chatgpt_account_id)
    if not account_id:
        raise ValueError("缺少 chatgpt_account_id，无法测试 Codex 接口")

    chosen_proxy = proxy if proxy is not None else pick_proxy()
    session = Session(impersonate=IMPERSONATE, timeout=min(timeout, REQUEST_TIMEOUT))
    if chosen_proxy:
        session.proxies = {"http": chosen_proxy, "https": chosen_proxy}

    headers = _build_oauth_headers(token, account_id)
    started = time.time()
    response = session.post(
        CHATGPT_CODEX_API,
        headers=headers,
        json=build_test_payload(test_model, test_message),
        timeout=timeout,
    )

    if response.status_code != 200:
        body_text = response.text[:500]
        return {
            "ok": False,
            "model": test_model,
            "message": test_message,
            "statusCode": response.status_code,
            "reply": "",
            "error": f"API 返回 {response.status_code}: {body_text}",
            "latencyMs": int((time.time() - started) * 1000),
        }

    parsed = _parse_sse_text(response.text)
    return {
        "ok": bool(parsed["ok"]),
        "model": test_model,
        "message": test_message,
        "statusCode": response.status_code,
        "reply": parsed["reply"],
        "error": parsed["error"],
        "latencyMs": int((time.time() - started) * 1000),
    }
