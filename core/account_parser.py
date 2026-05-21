# -*- coding: utf-8 -*-
"""解析后台导入的邮箱素材与 ChatGPT OAuth（sub2api）账号。"""
from __future__ import annotations

import json
import re
from typing import Any

from core.outlook_client import OutlookAccount

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def first_non_empty(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def parse_material_line(line: str) -> OutlookAccount:
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", line)
    if not email_match:
        raise ValueError("未找到邮箱")
    line = line[email_match.start():].strip()
    parts = [item.strip() for item in line.split("----")]
    if len(parts) != 4:
        raise ValueError("邮箱素材必须是 email----password----clientId----refreshToken 四段")
    email, password, client_id, refresh_token = parts
    if not EMAIL_PATTERN.match(email):
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


def parse_bulk_email_material(text: str) -> tuple[list[dict[str, str]], int]:
    records: list[dict[str, str]] = []
    skipped = 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            account = parse_material_line(line)
            records.append(
                {
                    "account_type": "email",
                    "email": account.email,
                    "password": account.password,
                    "client_id": account.client_id,
                    "refresh_token": account.refresh_token,
                    "material": "----".join(
                        [account.email, account.password, account.client_id, account.refresh_token]
                    ),
                    "oauth_data": "",
                }
            )
        except ValueError:
            skipped += 1
    if not records:
        raise ValueError("没有可导入的邮箱账号")
    return records, skipped


def normalize_oauth_record(item: dict[str, Any]) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError("OAuth 账号必须是 JSON 对象")

    credentials = item.get("credentials")
    if not isinstance(credentials, dict):
        credentials = {}

    access_token = first_non_empty(
        credentials.get("access_token"),
        credentials.get("accessToken"),
        item.get("access_token"),
        item.get("accessToken"),
    )
    if not access_token:
        raise ValueError("缺少 access_token")

    email = first_non_empty(
        credentials.get("email"),
        item.get("email"),
        item.get("name"),
    )
    if not email or "@" not in email:
        email = first_non_empty(item.get("name"), "oauth-account")

    chatgpt_account_id = first_non_empty(
        credentials.get("chatgpt_account_id"),
        credentials.get("chatgptAccountId"),
        credentials.get("account_id"),
        item.get("chatgpt_account_id"),
        item.get("chatgptAccountId"),
    )
    chatgpt_user_id = first_non_empty(
        credentials.get("chatgpt_user_id"),
        credentials.get("chatgptUserId"),
        item.get("chatgpt_user_id"),
        item.get("chatgptUserId"),
    )

    oauth_data = {
        "access_token": access_token,
        "chatgpt_account_id": chatgpt_account_id,
        "chatgpt_user_id": chatgpt_user_id,
        "email": email,
        "refresh_token": first_non_empty(
            credentials.get("refresh_token"),
            credentials.get("refreshToken"),
            item.get("refresh_token"),
            item.get("refreshToken"),
        ),
        "plan_type": first_non_empty(
            credentials.get("plan_type"),
            credentials.get("planType"),
            item.get("plan_type"),
            item.get("planType"),
        ),
    }

    return {
        "account_type": "oauth",
        "email": email,
        "password": "",
        "client_id": "",
        "refresh_token": oauth_data["refresh_token"],
        "material": json.dumps(item, ensure_ascii=False),
        "oauth_data": json.dumps(oauth_data, ensure_ascii=False),
    }


def _extract_oauth_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        raise ValueError("OAuth 导入内容必须是 JSON 对象或数组")

    accounts = data.get("accounts")
    if isinstance(accounts, list):
        return [item for item in accounts if isinstance(item, dict)]

    if data.get("type") == "oauth" or isinstance(data.get("credentials"), dict):
        return [data]

    if first_non_empty(data.get("access_token"), data.get("accessToken")):
        return [data]

    raise ValueError("无法识别的 OAuth JSON 格式，请使用 sub2api 账号或单行 OAuth JSON")


def parse_bulk_oauth_material(text: str) -> tuple[list[dict[str, str]], int]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("没有可导入的 OAuth 账号")

    records: list[dict[str, str]] = []
    skipped = 0

    if raw.startswith("{") or raw.startswith("["):
        try:
            data = json.loads(raw)
            for item in _extract_oauth_items(data):
                try:
                    records.append(normalize_oauth_record(item))
                except ValueError:
                    skipped += 1
            if records:
                return records, skipped
        except json.JSONDecodeError:
            pass

    for line in raw.splitlines():
        piece = line.strip()
        if not piece or piece.startswith("#"):
            continue
        if not piece.startswith("{"):
            skipped += 1
            continue
        try:
            item = json.loads(piece)
            if isinstance(item, dict) and "accounts" in item and isinstance(item["accounts"], list):
                for account in item["accounts"]:
                    try:
                        records.append(normalize_oauth_record(account))
                    except ValueError:
                        skipped += 1
            else:
                records.append(normalize_oauth_record(item))
        except (json.JSONDecodeError, ValueError, TypeError):
            skipped += 1

    if not records:
        raise ValueError("没有可导入的 OAuth 账号")
    return records, skipped


def parse_account_import(material: str, account_type: str) -> tuple[list[dict[str, str]], int]:
    normalized = (account_type or "email").strip().lower()
    if normalized in {"oauth", "chatgpt_oauth", "chatgpt-oauth"}:
        return parse_bulk_oauth_material(material)
    if normalized in {"email", "outlook"}:
        return parse_bulk_email_material(material)
    raise ValueError("不支持的账号类型，请选择 email 或 oauth")
