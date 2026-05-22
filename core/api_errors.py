# -*- coding: utf-8 -*-
"""将 API 异常转为面向用户的中/英文提示。"""
from __future__ import annotations

import re
import sqlite3
from typing import Callable

PatternReplacer = str | Callable[[re.Match[str]], str]


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def get_request_lang(default: str = "zh") -> str:
    try:
        from flask import has_request_context, request

        if has_request_context():
            lang = (request.headers.get("X-Client-Lang") or "").strip().lower()
            if lang.startswith("en"):
                return "en"
    except Exception:
        pass
    return default


_FALLBACK_ZH = "操作失败，请稍后重试"
_FALLBACK_EN = "Operation failed. Please try again."


_EXACT_ZH_TO_EN: dict[str, str] = {
    "卡密不存在": "Card key not found",
    "卡密已被使用": "Card key has already been used",
    "卡密不能为空": "Card key cannot be empty",
    "卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位": "Invalid card key format: PP uses Codex-P + 20 chars, GO uses Codex-G + 20 chars",
    "卡密格式不正确：PP 为 Codex-P + 20 位，GO 为 Codex-G + 20 位（旧版 Codex- + 16 位仍可用）": "Invalid card key format: PP uses Codex-P + 20 chars, GO uses Codex-G + 20 chars (legacy Codex- + 16 chars still supported)",
    "缺少或非法 client id": "Missing or invalid client id",
    "未找到邮箱": "Email not found",
    "邮箱素材必须是 email----password----clientId----refreshToken 四段": "Mailbox material must be email----password----clientId----refreshToken",
    "邮箱格式不正确": "Invalid email format",
    "没有可导入的账号素材": "No account material to import",
    "rows 格式不正确": "Invalid rows payload",
    "不支持的导出格式": "Unsupported export format",
    "没有可运行的账号": "No runnable accounts",
    "请先勾选要导出的账号": "Select at least one account to export",
    "未授权或登录已过期": "Unauthorized or session expired",
    "账号不存在": "Account not found",
    "不支持的操作": "Unsupported action",
    "缺少 row_id": "Missing row_id",
    "管理员密码错误": "Incorrect admin password",
    "系统繁忙，请稍后重试": "System is busy. Please try again later.",
    "数据库繁忙，请稍后重试": "Database is busy. Please try again later.",
    "数据库异常，请联系管理员": "Database error. Please contact the administrator.",
    "数据库结构异常，请重启服务": "Database schema error. Please restart the service.",
    "数据冲突，请刷新后重试": "Data conflict. Please refresh and try again.",
    "数据关联异常，请刷新后重试": "Data relation error. Please refresh and try again.",
    "数据库操作失败，请稍后重试": "Database operation failed. Please try again later.",
    "读取失败：验证码已超过2分钟": "Failed to read OTP: code is older than 2 minutes",
    "读取失败：2分钟内未收到验证码": "Failed to read OTP: no code received within 2 minutes",
    "读取失败：未知错误": "Failed to read OTP: unknown error",
}

_EXACT_EN_TO_ZH = {value: key for key, value in _EXACT_ZH_TO_EN.items()}


_TECH_ZH: dict[str, str] = {
    "cannot rollback - no transaction is active": "系统繁忙，请稍后重试",
    "database is locked": "数据库繁忙，请稍后重试",
    "database disk image is malformed": "数据库异常，请联系管理员",
    "no such table": "数据库结构异常，请重启服务",
    "no such column": "数据库结构异常，请重启服务",
    "unique constraint failed": "数据冲突，请刷新后重试",
    "foreign key constraint failed": "数据关联异常，请刷新后重试",
    "http error 403": "HTTP 403 禁止访问（登录可能已失效，请点「开始登录」）",
    "http error 401": "HTTP 401 未授权（请重新登录或刷新 token）",
    "http error 429": "HTTP 429 请求过于频繁，请稍后再试",
    "http error 500": "HTTP 500 上游服务错误",
    "http error 502": "HTTP 502 上游网关错误",
    "http error 503": "HTTP 503 服务暂时不可用",
    "failed to fetch": "网络请求失败（连接中断或 502，请稍后重试）",
    "notimplementederror": "测试引擎版本过旧，请重启 Docker 容器",
}

_TECH_EN: dict[str, str] = {
    key: _EXACT_ZH_TO_EN.get(value, value) for key, value in _TECH_ZH.items()
}


def _pattern_no_pool_accounts(match: re.Match[str]) -> str:
    pool = match.group(1)
    return (
        f"No available {pool} accounts that passed testing. "
        "Please try again later or contact the administrator."
    )


def _pattern_pool_mismatch(match: re.Match[str]) -> str:
    pool = match.group(1)
    return f"Card key type mismatch: this key belongs to the {pool} pool."


def _pattern_missing_fields(match: re.Match[str]) -> str:
    return f"Missing fields: {match.group(1)}"


def _pattern_not_logged_in(match: re.Match[str]) -> str:
    return f"The following accounts are not logged in yet: {match.group(1)}"


def _pattern_read_otp(match: re.Match[str]) -> str:
    detail = translate_user_message(match.group(1), "en")
    return f"Failed to read OTP: {detail.removeprefix('Failed to read OTP: ')}" if detail.startswith("Failed to read OTP:") else f"Failed to read OTP: {detail}"


def _pattern_no_pool_accounts_zh(match: re.Match[str]) -> str:
    pool = match.group(1)
    return f"暂无 {pool} 测试通过的可用账号，请稍后再试或联系管理员"


def _pattern_pool_mismatch_zh(match: re.Match[str]) -> str:
    pool = match.group(1)
    return f"卡密类型不匹配：该卡密属于 {pool} 池"


def _pattern_missing_fields_zh(match: re.Match[str]) -> str:
    return f"缺少字段: {match.group(1)}"


def _pattern_not_logged_in_zh(match: re.Match[str]) -> str:
    return f"以下账号还没有成功登录: {match.group(1)}"


def _pattern_read_otp_zh(match: re.Match[str]) -> str:
    detail = translate_user_message(match.group(1), "zh")
    return detail if detail.startswith("读取失败：") else f"读取失败：{detail}"


_PATTERN_ZH_TO_EN: list[tuple[re.Pattern[str], PatternReplacer]] = [
    (re.compile(r"^暂无 (PP|GO) 测试通过的可用账号，请稍后再试或联系管理员$"), _pattern_no_pool_accounts),
    (re.compile(r"^卡密类型不匹配：该卡密属于 (PP|GO) 池$"), _pattern_pool_mismatch),
    (re.compile(r"^缺少字段: (.+)$"), _pattern_missing_fields),
    (re.compile(r"^以下账号还没有成功登录: (.+)$"), _pattern_not_logged_in),
    (re.compile(r"^读取失败：(.+)$"), _pattern_read_otp),
]

_PATTERN_EN_TO_ZH: list[tuple[re.Pattern[str], PatternReplacer]] = [
    (
        re.compile(
            r"^No available (PP|GO) accounts that passed testing\. "
            r"Please try again later or contact the administrator\.$"
        ),
        _pattern_no_pool_accounts_zh,
    ),
    (re.compile(r"^Card key type mismatch: this key belongs to the (PP|GO) pool\.$"), _pattern_pool_mismatch_zh),
    (re.compile(r"^Missing fields: (.+)$"), _pattern_missing_fields_zh),
    (
        re.compile(r"^The following accounts are not logged in yet: (.+)$"),
        _pattern_not_logged_in_zh,
    ),
    (re.compile(r"^Failed to read OTP: (.+)$"), _pattern_read_otp_zh),
]


def _apply_patterns(message: str, patterns: list[tuple[re.Pattern[str], PatternReplacer]]) -> str | None:
    for pattern, replacer in patterns:
        match = pattern.fullmatch(message)
        if not match:
            continue
        return replacer(match) if callable(replacer) else match.expand(replacer)
    return None


def translate_user_message(message: str, lang: str) -> str:
    text = str(message or "").strip()
    normalized_lang = "en" if str(lang or "").lower().startswith("en") else "zh"
    if not text:
        return _FALLBACK_EN if normalized_lang == "en" else _FALLBACK_ZH

    has_cjk = _contains_cjk(text)
    if normalized_lang == "en":
        if not has_cjk:
            return text
        if text in _EXACT_ZH_TO_EN:
            return _EXACT_ZH_TO_EN[text]
        patterned = _apply_patterns(text, _PATTERN_ZH_TO_EN)
        if patterned:
            return patterned
        return _FALLBACK_EN

    if has_cjk:
        return text
    if text in _EXACT_EN_TO_ZH:
        return _EXACT_EN_TO_ZH[text]
    patterned = _apply_patterns(text, _PATTERN_EN_TO_ZH)
    if patterned:
        return patterned
    lowered = text.lower()
    for key, translated in _TECH_ZH.items():
        if key in lowered:
            return translated
    return text


def public_error_message(
    exc: BaseException,
    *,
    lang: str | None = None,
    fallback: str | None = None,
) -> str:
    resolved_lang = lang or get_request_lang()
    default_fallback = _FALLBACK_EN if resolved_lang == "en" else _FALLBACK_ZH
    resolved_fallback = fallback or default_fallback

    if isinstance(exc, ValueError):
        message = str(exc).strip()
        if message:
            return translate_user_message(message, resolved_lang)

    message = str(exc).strip()
    if not message:
        return resolved_fallback
    if _contains_cjk(message):
        return translate_user_message(message, resolved_lang)

    lowered = message.lower()
    tech_map = _TECH_EN if resolved_lang == "en" else _TECH_ZH
    for key, translated in tech_map.items():
        if key in lowered:
            return translated

    if isinstance(exc, sqlite3.Error):
        return translate_user_message("数据库操作失败，请稍后重试", resolved_lang)

    # 未知英文技术错误：保留原文，避免管理后台只看到「操作失败」
    return translate_user_message(message, resolved_lang)
