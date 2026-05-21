# -*- coding: utf-8 -*-
"""代理池连通性检测。"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from curl_cffi.requests import Session

from config import IMPERSONATE
from core.app_settings import parse_proxy_pool_text

PROXY_TEST_TIMEOUT = 18
IPIFY_URL = "https://api.ipify.org?format=json"
CHATGPT_URL = "https://chatgpt.com/"


def mask_proxy(proxy: str) -> str:
    text = (proxy or "").strip()
    if not text:
        return "直连"
    try:
        scheme, rest = text.split("://", 1)
        host = rest.split("@")[-1]
        return f"{scheme}://...@{host}"
    except Exception:
        return "已配置"


def test_direct_connection(*, timeout: float = PROXY_TEST_TIMEOUT) -> dict[str, Any]:
    started = time.time()
    try:
        session = Session(impersonate=IMPERSONATE, timeout=timeout)
        ip_resp = session.get(IPIFY_URL, timeout=timeout)
        ip_resp.raise_for_status()
        exit_ip = str(ip_resp.json().get("ip") or "").strip()
        chatgpt_resp = session.get(CHATGPT_URL, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.time() - started) * 1000)
        chatgpt_ok = chatgpt_resp.status_code < 500
        return {
            "proxy": "",
            "label": "直连（无代理）",
            "ok": bool(exit_ip) and chatgpt_ok,
            "latencyMs": latency_ms,
            "exitIp": exit_ip,
            "chatgptStatus": chatgpt_resp.status_code,
            "chatgptOk": chatgpt_ok,
        }
    except Exception as exc:
        return {
            "proxy": "",
            "label": "直连（无代理）",
            "ok": False,
            "latencyMs": int((time.time() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def test_single_proxy(proxy: str, *, timeout: float = PROXY_TEST_TIMEOUT) -> dict[str, Any]:
    started = time.time()
    label = mask_proxy(proxy)
    try:
        session = Session(impersonate=IMPERSONATE, timeout=timeout)
        session.proxies = {"http": proxy, "https": proxy}
        ip_resp = session.get(IPIFY_URL, timeout=timeout)
        ip_resp.raise_for_status()
        exit_ip = str(ip_resp.json().get("ip") or "").strip()
        chatgpt_resp = session.get(CHATGPT_URL, timeout=timeout, allow_redirects=True)
        latency_ms = int((time.time() - started) * 1000)
        chatgpt_ok = chatgpt_resp.status_code < 500
        return {
            "proxy": proxy,
            "label": label,
            "ok": bool(exit_ip) and chatgpt_ok,
            "latencyMs": latency_ms,
            "exitIp": exit_ip,
            "chatgptStatus": chatgpt_resp.status_code,
            "chatgptOk": chatgpt_ok,
        }
    except Exception as exc:
        return {
            "proxy": proxy,
            "label": label,
            "ok": False,
            "latencyMs": int((time.time() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }


def test_proxy_pool(
    proxies: list[str] | None = None,
    *,
    proxy_pool_text: str | None = None,
    max_workers: int = 5,
) -> dict[str, Any]:
    if proxy_pool_text is not None:
        pool = parse_proxy_pool_text(proxy_pool_text)
    else:
        pool = [str(item).strip() for item in (proxies or []) if str(item).strip()]

    started = time.time()
    results: list[dict[str, Any]] = []

    if not pool:
        direct = test_direct_connection()
        results.append(direct)
        return {
            "total": 0,
            "ok": 1 if direct.get("ok") else 0,
            "failed": 0 if direct.get("ok") else 1,
            "directOnly": True,
            "durationMs": int((time.time() - started) * 1000),
            "results": results,
            "summary": "代理池为空，已测试本机直连",
        }

    workers = max(1, min(max_workers, len(pool)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(test_single_proxy, proxy): proxy for proxy in pool}
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda item: (not item.get("ok"), item.get("label") or ""))
    ok_count = sum(1 for item in results if item.get("ok"))
    failed_count = len(results) - ok_count
    return {
        "total": len(results),
        "ok": ok_count,
        "failed": failed_count,
        "directOnly": False,
        "durationMs": int((time.time() - started) * 1000),
        "results": results,
        "summary": f"可用 {ok_count}/{len(results)}，不可用 {failed_count}",
    }
