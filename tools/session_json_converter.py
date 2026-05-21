#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch convert ChatGPT Web /api/auth/session style JSON into import files.

This mirrors https://gtxx3600.github.io/GPTSession2CPAandSub2API/:
  - sub2api
  - CPA
  - Cockpit
  - 9router
  - AxonHub

Default input is this project's saved registration output:
  注册成功的邮箱.json
  accounts/*/注册成功账号.json
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "converted_sessions"
FORMATS = ("sub2api", "cpa", "cockpit", "9router", "axonhub")
AXONHUB_PLACEHOLDER_REFRESH_TOKEN = "__missing_refresh_token__"


def is_plain_object(value: Any) -> bool:
    return isinstance(value, dict)


def first_non_empty(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def nested_get(value: Any, *keys: str) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def decode_base64url(value: str) -> bytes:
    padded = value + ("=" * ((4 - len(value) % 4) % 4))
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def encode_base64url_json(value: Any) -> str:
    raw = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def parse_jwt_payload(token: str | None) -> dict:
    if not isinstance(token, str) or not token.strip():
        return {}
    segments = token.split(".")
    if len(segments) < 2:
        return {}
    try:
        payload = json.loads(decode_base64url(segments[1]).decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def get_openai_auth_section(payload: dict) -> dict:
    auth = payload.get("https://api.openai.com/auth")
    return auth if isinstance(auth, dict) else {}


def get_openai_profile_section(payload: dict) -> dict:
    profile = payload.get("https://api.openai.com/profile")
    return profile if isinstance(profile, dict) else {}


def normalize_timestamp(value: Any) -> str | None:
    if isinstance(value, datetime):
        date = value
    elif isinstance(value, (int, float)) and math.isfinite(value):
        seconds = value / 1000 if value > 1e11 else value
        date = datetime.fromtimestamp(seconds, timezone.utc)
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            date = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)
    return date.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp_from_unix_seconds(value: Any) -> str | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric):
        return None
    return normalize_timestamp(numeric)


def epoch_seconds_from_value(value: Any) -> int:
    if value in (None, ""):
        return 0
    if isinstance(value, (int, float)) and math.isfinite(value):
        return int(value / 1000 if value > 1e11 else value)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return 0
        return int(parsed.timestamp())
    return 0


def build_synthetic_codex_id_token(
    email: str | None,
    account_id: str | None,
    plan_type: str | None,
    user_id: str | None,
    expires_at: str | None,
) -> str | None:
    if not account_id:
        return None

    now = int(datetime.now(timezone.utc).timestamp())
    expires = epoch_seconds_from_value(expires_at) or now + 90 * 24 * 60 * 60
    auth_info: dict[str, Any] = {"chatgpt_account_id": account_id}
    if plan_type:
        auth_info["chatgpt_plan_type"] = plan_type
    if user_id:
        auth_info["chatgpt_user_id"] = user_id
        auth_info["user_id"] = user_id

    payload: dict[str, Any] = {
        "iat": now,
        "exp": expires,
        "https://api.openai.com/auth": auth_info,
    }
    if email:
        payload["email"] = email

    return ".".join([
        encode_base64url_json({"alg": "none", "typ": "JWT", "cpa_synthetic": True}),
        encode_base64url_json(payload),
        "synthetic",
    ])


def get_expires_in(expires_at: str | None, now: datetime) -> int | None:
    if not expires_at:
        return None
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    return max(0, int((expires - now).total_seconds()))


def get_axonhub_last_refresh(expires_at: str | None, now: datetime) -> str:
    if not expires_at:
        return normalize_timestamp(now) or ""
    try:
        expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return normalize_timestamp(now) or ""
    return normalize_timestamp(expires.timestamp() - 60 * 60) or ""


def strip_unavailable(value: Any) -> Any:
    if isinstance(value, list):
        cleaned = [strip_unavailable(item) for item in value]
        return [item for item in cleaned if item is not None]
    if isinstance(value, dict):
        cleaned = {
            key: strip_unavailable(item)
            for key, item in value.items()
        }
        cleaned = {
            key: item
            for key, item in cleaned.items()
            if item is not None
        }
        return cleaned or None
    if value is None or value == "":
        return None
    return value


def to_email_key(email: str | None) -> str | None:
    if not isinstance(email, str):
        return None
    cleaned = re.sub(r"[^a-z0-9]+", "_", email.strip().lower())
    cleaned = cleaned.strip("_")
    return cleaned or None


def sanitize_file_token(value: str | None, fallback: str = "chatgpt-session") -> str:
    base = first_non_empty(value, fallback) or fallback
    base = re.sub(r"\.[^.]+$", "", base)
    base = re.sub(r'[\\/:*?"<>|]+', "-", base)
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"-+", "-", base).strip("-").lower()
    return (base[:80] or fallback)


def get_timestamp_token(date: datetime | None = None) -> str:
    date = date or datetime.now()
    return date.strftime("%Y-%m-%d_%H-%M-%S")


def collect_session_like_objects(value: Any, source_name: str = "pasted-json") -> list[dict]:
    found: list[dict] = []
    visited: set[int] = set()

    def visit(item: Any, path: str) -> None:
        if not isinstance(item, (dict, list)):
            return
        if isinstance(item, dict):
            item_id = id(item)
            if item_id in visited:
                return
            visited.add(item_id)

            token = first_non_empty(
                item.get("accessToken"),
                item.get("access_token"),
                nested_get(item, "token", "accessToken"),
                nested_get(item, "token", "access_token"),
                nested_get(item, "credentials", "accessToken"),
                nested_get(item, "credentials", "access_token"),
            )
            has_identity = (
                isinstance(item.get("user"), dict)
                or first_non_empty(
                    item.get("email"),
                    item.get("name"),
                    nested_get(item, "providerSpecificData", "chatgptAccountId"),
                    nested_get(item, "providerSpecificData", "chatgpt_account_id"),
                    item.get("id"),
                )
            )
            if token and has_identity:
                found.append({"value": item, "sourceName": source_name, "path": path})
                return

            for key, child in item.items():
                if key in {"accessToken", "access_token", "sessionToken"}:
                    continue
                visit(child, f"{path}.{key}")
            return

        for index, child in enumerate(item):
            visit(child, f"{path}[{index}]")

    visit(value, "$")
    return found


def convert_session(record: dict, now: datetime, source_name: str = "pasted-json", source_path: str | None = None) -> dict:
    if not isinstance(record, dict):
        raise ValueError("session 不是 JSON 对象")

    access_token = first_non_empty(
        record.get("accessToken"),
        record.get("access_token"),
        nested_get(record, "token", "accessToken"),
        nested_get(record, "token", "access_token"),
        nested_get(record, "credentials", "accessToken"),
        nested_get(record, "credentials", "access_token"),
    )
    if not access_token:
        raise ValueError("缺少 accessToken")

    session_token = first_non_empty(
        record.get("sessionToken"),
        record.get("session_token"),
        nested_get(record, "token", "sessionToken"),
        nested_get(record, "token", "session_token"),
        nested_get(record, "credentials", "session_token"),
    )
    refresh_token = first_non_empty(
        record.get("refreshToken"),
        record.get("refresh_token"),
        nested_get(record, "token", "refreshToken"),
        nested_get(record, "token", "refresh_token"),
        nested_get(record, "credentials", "refresh_token"),
    )
    input_id_token = first_non_empty(
        record.get("idToken"),
        record.get("id_token"),
        nested_get(record, "token", "idToken"),
        nested_get(record, "token", "id_token"),
        nested_get(record, "credentials", "id_token"),
    )

    payload = parse_jwt_payload(access_token)
    id_payload = parse_jwt_payload(input_id_token)
    auth = get_openai_auth_section(payload)
    id_auth = get_openai_auth_section(id_payload)
    profile = get_openai_profile_section(payload)

    expires_at = first_non_empty(
        timestamp_from_unix_seconds(payload.get("exp")) if payload else None,
        normalize_timestamp(record.get("expires")),
        normalize_timestamp(record.get("expiresAt")),
        normalize_timestamp(record.get("expired")),
        normalize_timestamp(record.get("expires_at")),
    )
    email = first_non_empty(
        nested_get(record, "user", "email"),
        record.get("email"),
        nested_get(record, "credentials", "email"),
        nested_get(record, "providerSpecificData", "email"),
        profile.get("email"),
        id_payload.get("email"),
        payload.get("email"),
    )
    account_id = first_non_empty(
        nested_get(record, "account", "id"),
        record.get("account_id"),
        record.get("chatgptAccountId"),
        nested_get(record, "providerSpecificData", "chatgptAccountId"),
        nested_get(record, "providerSpecificData", "chatgpt_account_id"),
        nested_get(record, "credentials", "chatgpt_account_id"),
        auth.get("chatgpt_account_id"),
        id_auth.get("chatgpt_account_id"),
        record.get("id") if record.get("provider") == "codex" else None,
    )
    user_id = first_non_empty(
        nested_get(record, "user", "id"),
        record.get("user_id"),
        record.get("chatgptUserId"),
        nested_get(record, "providerSpecificData", "chatgptUserId"),
        nested_get(record, "providerSpecificData", "chatgpt_user_id"),
        auth.get("chatgpt_user_id"),
        auth.get("user_id"),
        id_auth.get("chatgpt_user_id"),
        id_auth.get("user_id"),
    )
    plan_type = first_non_empty(
        nested_get(record, "account", "planType"),
        nested_get(record, "account", "plan_type"),
        record.get("planType"),
        record.get("plan_type"),
        nested_get(record, "providerSpecificData", "chatgptPlanType"),
        nested_get(record, "providerSpecificData", "chatgpt_plan_type"),
        nested_get(record, "credentials", "plan_type"),
        auth.get("chatgpt_plan_type"),
        id_auth.get("chatgpt_plan_type"),
    )

    exported_at = normalize_timestamp(now)
    expires_in = get_expires_in(expires_at, now)
    source_type = "9router" if record.get("provider") == "codex" and record.get("authType") == "oauth" else "chatgpt_web_session"
    name = first_non_empty(email, source_name, "ChatGPT Account")
    synthetic_id_token = None if input_id_token else build_synthetic_codex_id_token(email, account_id, plan_type, user_id, expires_at)
    id_token = first_non_empty(input_id_token, synthetic_id_token)

    cpa = {
        key: value
        for key, value in {
            "type": "codex",
            "account_id": account_id,
            "chatgpt_account_id": account_id,
            "email": email,
            "name": name,
            "plan_type": plan_type,
            "chatgpt_plan_type": plan_type,
            "id_token": id_token,
            "id_token_synthetic": True if synthetic_id_token else None,
            "access_token": access_token,
            "refresh_token": refresh_token or "",
            "session_token": session_token,
            "last_refresh": exported_at,
            "expired": expires_at,
            "disabled": True if record.get("disabled") else None,
        }.items()
        if value is not None
    }

    cockpit = {
        "type": "codex",
        "id_token": id_token,
        "access_token": access_token,
        "refresh_token": refresh_token or "",
        "account_id": account_id,
        "last_refresh": exported_at,
        "email": email,
        "expired": expires_at,
        "account_note": first_non_empty(
            record.get("account_note"),
            record.get("accountInfo"),
            record.get("account_info"),
            record.get("note"),
            record.get("notes"),
            record.get("remark"),
        ),
    }

    sub2api_account = strip_unavailable({
        "name": first_non_empty(name, email, source_name, "ChatGPT Account"),
        "platform": "openai",
        "type": "oauth",
        "concurrency": 10,
        "priority": 1,
        "credentials": strip_unavailable({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "chatgpt_account_id": account_id,
            "chatgpt_user_id": user_id,
            "email": email,
            "expires_at": expires_at,
            "expires_in": expires_in,
            "plan_type": plan_type,
        }),
        "extra": {
            "email": email,
            "email_key": to_email_key(email),
            "name": name,
            "auth_provider": first_non_empty(record.get("authProvider"), record.get("auth_provider")),
            "source": source_type,
            "last_refresh": exported_at,
        },
    })

    try:
        priority = float(record.get("priority"))
        priority = int(priority) if priority.is_integer() else priority
    except (TypeError, ValueError, AttributeError):
        priority = 9
    is_active = record.get("isActive") if isinstance(record.get("isActive"), bool) else not bool(record.get("disabled"))
    created_at = normalize_timestamp(record.get("createdAt")) or exported_at
    updated_at = normalize_timestamp(record.get("updatedAt")) or exported_at
    nine_router = strip_unavailable({
        "accessToken": access_token,
        "refreshToken": refresh_token,
        "expiresAt": expires_at,
        "testStatus": first_non_empty(record.get("testStatus"), record.get("test_status"), "active"),
        "expiresIn": expires_in,
        "providerSpecificData": {
            "chatgptAccountId": account_id,
            "chatgptPlanType": plan_type,
        },
        "id": account_id,
        "provider": "codex",
        "authType": "oauth",
        "name": name,
        "email": email,
        "priority": priority,
        "isActive": is_active,
        "createdAt": created_at,
        "updatedAt": updated_at,
    })

    axonhub_refresh_token = refresh_token or AXONHUB_PLACEHOLDER_REFRESH_TOKEN
    axonhub = strip_unavailable({
        "auth_mode": "chatgpt",
        "last_refresh": get_axonhub_last_refresh(expires_at, now),
        "tokens": {
            "access_token": access_token,
            "refresh_token": axonhub_refresh_token,
            "id_token": id_token,
        },
        "axonhub_refresh_token_placeholder": None if refresh_token else True,
        "axonhub_note": None if refresh_token else "refresh_token is a placeholder; access_token works only until it expires.",
    })

    return {
        "sourceName": source_name,
        "sourcePath": source_path,
        "email": email,
        "name": name,
        "expiresAt": expires_at,
        "cpa": cpa,
        "cockpit": strip_unavailable(cockpit) or {},
        "nineRouter": nine_router,
        "axonHub": axonhub,
        "sub2apiAccount": sub2api_account,
    }


def build_output_document(converted: list[dict], output_format: str, now: datetime) -> Any:
    if output_format == "sub2api":
        return {
            "exported_at": normalize_timestamp(now),
            "proxies": [],
            "accounts": [item["sub2apiAccount"] for item in converted],
        }
    if output_format == "cpa":
        rows = [item["cpa"] for item in converted]
    elif output_format == "cockpit":
        rows = [item["cockpit"] for item in converted]
    elif output_format == "9router":
        rows = [item["nineRouter"] for item in converted]
    elif output_format == "axonhub":
        rows = [item["axonHub"] for item in converted]
    else:
        raise ValueError(f"不支持的格式: {output_format}")
    return rows[0] if len(rows) == 1 else rows


def project_default_inputs() -> list[Path]:
    paths: list[Path] = []
    root_accounts = PROJECT_ROOT / "注册成功的邮箱.json"
    if root_accounts.exists():
        paths.append(root_accounts)
    paths.extend(sorted((PROJECT_ROOT / "accounts").glob("*/注册成功账号.json")))
    return paths


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def collect_from_files(paths: list[Path], quiet_empty: bool = False) -> tuple[list[dict], list[dict]]:
    documents: list[dict] = []
    skipped: list[dict] = []
    for path in paths:
        try:
            parsed = load_json(path)
        except Exception as exc:
            skipped.append({"sourceName": str(path), "path": "$", "reason": f"无法读取 JSON: {exc}"})
            continue

        found = collect_session_like_objects(parsed, str(path))
        if not found and not quiet_empty:
            skipped.append({
                "sourceName": str(path),
                "path": "$",
                "reason": "未找到包含 accessToken 和 user/email 的 session 对象",
            })
        documents.extend(found)
    return documents, skipped


def dedupe_documents(documents: list[dict]) -> list[dict]:
    seen: set[tuple[str | None, str | None]] = set()
    result: list[dict] = []
    for item in documents:
        value = item["value"]
        access_token = first_non_empty(value.get("accessToken"), value.get("access_token"))
        email = first_non_empty(nested_get(value, "user", "email"), value.get("email"))
        key = (email, access_token)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="批量转换 ChatGPT session JSON 为 CPA/sub2api/Cockpit/9router/AxonHub 导入文件")
    parser.add_argument("inputs", nargs="*", type=Path, help="输入 JSON 文件/目录；留空则读取本项目注册成功账号")
    parser.add_argument("-f", "--format", choices=FORMATS + ("all",), default="all", help="输出格式，默认 all")
    parser.add_argument("-o", "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="输出目录")
    parser.add_argument("--no-dedupe", action="store_true", help="不按 email+access_token 去重")
    parser.add_argument("--strict", action="store_true", help="存在跳过项时返回非 0")
    args = parser.parse_args()

    input_paths: list[Path] = []
    if args.inputs:
        for item in args.inputs:
            path = item if item.is_absolute() else (Path.cwd() / item)
            if path.is_dir():
                input_paths.extend(sorted(path.rglob("*.json")))
            else:
                input_paths.append(path)
    else:
        input_paths = project_default_inputs()

    if not input_paths:
        print("没有找到输入 JSON。可传入文件/目录，或先生成项目里的注册成功账号。")
        return 1

    documents, skipped = collect_from_files(input_paths, quiet_empty=not bool(args.inputs))
    if not args.no_dedupe:
        documents = dedupe_documents(documents)

    now = datetime.now(timezone.utc)
    converted: list[dict] = []
    for item in documents:
        try:
            converted.append(convert_session(
                item["value"],
                now=now,
                source_name=item.get("sourceName") or "pasted-json",
                source_path=item.get("path"),
            ))
        except Exception as exc:
            skipped.append({
                "sourceName": item.get("sourceName"),
                "path": item.get("path"),
                "reason": str(exc),
            })

    if not converted:
        print(f"没有可转换账号。跳过 {len(skipped)} 项。")
        for item in skipped[:10]:
            print(f"- {item.get('sourceName')} {item.get('path')}: {item.get('reason')}")
        return 1

    formats = FORMATS if args.format == "all" else (args.format,)
    ts = get_timestamp_token()
    for output_format in formats:
        output = build_output_document(converted, output_format, now)
        first = converted[0]
        base = sanitize_file_token(first.get("email") or first.get("name") or output_format)
        out_path = args.output_dir / f"{base}.{output_format}.{ts}.json"
        write_json(out_path, output)
        print(f"[OK] {output_format}: {len(converted)} 个账号 -> {out_path}")

    if skipped:
        issues_path = args.output_dir / f"conversion-skipped.{ts}.json"
        write_json(issues_path, skipped)
        print(f"[WARN] 跳过 {len(skipped)} 项，详情 -> {issues_path}")

    return 2 if args.strict and skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
