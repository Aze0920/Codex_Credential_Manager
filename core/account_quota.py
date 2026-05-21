# -*- coding: utf-8 -*-
"""查询 ChatGPT Codex 账号额度（wham/usage）。"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from curl_cffi.requests import Session

from config import IMPERSONATE, REQUEST_TIMEOUT, USER_AGENT, pick_proxy

WHAM_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"


def _format_reset(seconds: int | float | None) -> str:
    try:
        value = int(seconds or 0)
    except (TypeError, ValueError):
        return "-"
    if value <= 0:
        return "即将重置"
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}天{hours}时"
    if hours:
        return f"{hours}时{minutes}分"
    if minutes:
        return f"{minutes}分{secs}秒"
    return f"{secs}秒"


def _window_summary(window: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(window, dict):
        return {}
    used_percent = window.get("used_percent")
    try:
        used = float(used_percent)
    except (TypeError, ValueError):
        used = None
    return {
        "usedPercent": used,
        "resetAfterSeconds": window.get("reset_after_seconds"),
        "resetAt": window.get("reset_at"),
        "limitWindowSeconds": window.get("limit_window_seconds"),
    }


def summarize_quota(data: dict[str, Any]) -> dict[str, Any]:
    rate_limit = data.get("rate_limit") if isinstance(data.get("rate_limit"), dict) else {}
    primary = _window_summary(rate_limit.get("primary_window"))
    secondary = _window_summary(rate_limit.get("secondary_window"))
    credits = data.get("credits") if isinstance(data.get("credits"), dict) else {}
    spend = data.get("spend_control") if isinstance(data.get("spend_control"), dict) else {}

    summary_parts: list[str] = []
    if primary.get("usedPercent") is not None:
        summary_parts.append(f"5h {primary['usedPercent']:.0f}%")
    if secondary.get("usedPercent") is not None:
        summary_parts.append(f"周 {secondary['usedPercent']:.0f}%")
    plan_type = str(data.get("plan_type") or "").strip()
    if plan_type:
        summary_parts.append(plan_type)

    return {
        "summary": " | ".join(summary_parts) if summary_parts else "-",
        "planType": plan_type,
        "email": str(data.get("email") or ""),
        "primaryWindow": primary,
        "secondaryWindow": secondary,
        "limitReached": bool(rate_limit.get("limit_reached")),
        "allowed": bool(rate_limit.get("allowed", True)),
        "creditsBalance": str(credits.get("balance") or ""),
        "creditsUnlimited": bool(credits.get("unlimited")),
        "spendReached": bool(spend.get("reached")),
        "primaryResetText": _format_reset(primary.get("resetAfterSeconds")),
        "secondaryResetText": _format_reset(secondary.get("resetAfterSeconds")),
        "queriedAt": datetime.now(timezone.utc).isoformat(),
    }


def query_chatgpt_quota(
    access_token: str,
    *,
    chatgpt_account_id: str | None = None,
    proxy: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    token = (access_token or "").strip()
    if not token:
        raise ValueError("缺少 access_token")

    account_id = (chatgpt_account_id or "").strip()
    if not account_id:
        from core.openai_oauth import _extract_user_info

        account_id = _extract_user_info(token).get("chatgpt_account_id") or ""
    if not account_id:
        raise ValueError("缺少 chatgpt_account_id，无法查询额度")

    chosen_proxy = proxy if proxy is not None else pick_proxy()
    session = Session(impersonate=IMPERSONATE, timeout=min(timeout, REQUEST_TIMEOUT))
    if chosen_proxy:
        session.proxies = {"http": chosen_proxy, "https": chosen_proxy}

    started = time.time()
    response = session.get(
        WHAM_USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "ChatGPT-Account-Id": account_id,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        timeout=timeout,
    )
    latency_ms = int((time.time() - started) * 1000)

    if response.status_code != 200:
        return {
            "ok": False,
            "statusCode": response.status_code,
            "error": f"额度查询失败: HTTP {response.status_code} {response.text[:300]}",
            "latencyMs": latency_ms,
        }

    try:
        payload = response.json()
    except Exception as exc:
        return {
            "ok": False,
            "statusCode": response.status_code,
            "error": f"额度响应解析失败: {exc}",
            "latencyMs": latency_ms,
        }

    if not isinstance(payload, dict):
        return {
            "ok": False,
            "statusCode": response.status_code,
            "error": "额度响应格式不正确",
            "latencyMs": latency_ms,
        }

    summary = summarize_quota(payload)
    return {
        "ok": True,
        "statusCode": response.status_code,
        "latencyMs": latency_ms,
        "raw": payload,
        **summary,
    }
