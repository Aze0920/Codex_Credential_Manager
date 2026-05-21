# -*- coding: utf-8 -*-
"""应用运行时设置（后台密码、代理池），全部存入 SQLite。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

from core.card_store import delete_setting, get_setting, get_setting_json, init_db, set_setting, set_setting_json

SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "app_settings.json"
LOCK = threading.RLock()
PASSWORD_HASH_PREFIX = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
DEFAULT_TEST_MODELS = (
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.5",
    "gpt-5.3-codex",
    "gpt-5.2",
)
DEFAULT_TEST_MODEL = "gpt-5.3-codex"
DEFAULT_TEST_MESSAGE = "hi"


def _default_admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", "admin123")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _hash_admin_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    return f"{PASSWORD_HASH_PREFIX}${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def _is_password_hash(value: str) -> bool:
    return value.startswith(f"{PASSWORD_HASH_PREFIX}$")


def _verify_password_hash(candidate: str, stored: str) -> bool:
    try:
        prefix, iterations_str, salt_b64, digest_b64 = stored.split("$", 3)
        if prefix != PASSWORD_HASH_PREFIX:
            return False
        iterations = int(iterations_str)
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        candidate.encode("utf-8"),
        salt,
        iterations,
    )
    return secrets.compare_digest(actual, expected)


def _normalize_saved_password(value: str | None) -> str:
    return str(value or "").strip()


def _upgrade_password_storage_if_needed() -> None:
    saved = _normalize_saved_password(get_setting("admin_password"))
    if not saved:
        return
    if _is_password_hash(saved):
        return
    set_setting("admin_password", _hash_admin_password(saved))


def _migrate_json_settings_once() -> None:
    if not SETTINGS_PATH.exists():
        return
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    with LOCK:
        if data.get("admin_password") and not get_setting("admin_password"):
            migrated = _normalize_saved_password(str(data["admin_password"]))
            if migrated and migrated != _default_admin_password():
                set_setting("admin_password", _hash_admin_password(migrated))
        proxy_pool = data.get("proxy_pool")
        if isinstance(proxy_pool, list) and not get_setting("proxy_pool"):
            set_setting_json("proxy_pool", proxy_pool)
    backup = SETTINGS_PATH.with_suffix(".json.bak")
    try:
        if SETTINGS_PATH.exists():
            SETTINGS_PATH.replace(backup)
    except OSError:
        pass


def ensure_settings_ready() -> None:
    init_db()
    _migrate_json_settings_once()
    _upgrade_password_storage_if_needed()


def parse_proxy_pool_text(text: str) -> list[str]:
    proxies: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        proxies.append(line)
    return proxies


def verify_admin_password(candidate: str) -> bool:
    ensure_settings_ready()
    password = (candidate or "").strip()
    if not password:
        return False
    saved = _normalize_saved_password(get_setting("admin_password"))
    if saved:
        if _is_password_hash(saved):
            return _verify_password_hash(password, saved)
        if password == saved:
            set_setting("admin_password", _hash_admin_password(password))
            return True
        return False
    return password == _default_admin_password()


def reset_admin_password_to_default() -> None:
    ensure_settings_ready()
    delete_setting("admin_password")


def get_proxy_pool() -> list[str]:
    ensure_settings_ready()
    raw = get_setting_json("proxy_pool")
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def apply_runtime_settings() -> None:
    from config import proxy as proxy_config

    pool = get_proxy_pool()
    proxy_config.set_proxy_pool(pool)


def parse_test_models_text(text: str) -> list[str]:
    models: list[str] = []
    seen: set[str] = set()
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        models.append(line)
    return models


def get_test_settings() -> dict[str, Any]:
    ensure_settings_ready()
    from core.proxy_tester import mask_proxy

    raw_models = get_setting_json("test_models")
    if isinstance(raw_models, list):
        models = [str(item).strip() for item in raw_models if str(item).strip()]
    else:
        models = []
    if not models:
        models = list(DEFAULT_TEST_MODELS)
    default_model = (get_setting("default_test_model") or DEFAULT_TEST_MODEL).strip()
    if default_model not in models:
        default_model = models[0]
    default_message = (get_setting("default_test_message") or DEFAULT_TEST_MESSAGE).strip() or DEFAULT_TEST_MESSAGE
    proxy_options = [{"value": "", "label": "直连（无代理）"}]
    for item in get_proxy_pool():
        proxy_options.append({"value": item, "label": mask_proxy(item)})
    return {
        "models": models,
        "defaultModel": default_model,
        "defaultMessage": default_message,
        "testModelsText": "\n".join(models),
        "proxyOptions": proxy_options,
    }


def get_allowed_test_models() -> tuple[str, ...]:
    return tuple(get_test_settings()["models"])


def get_auto_test_settings() -> dict[str, Any]:
    from core.auto_test_scheduler import get_auto_test_interval_hours, get_runtime_status

    interval = get_auto_test_interval_hours()
    last_run = (get_setting("auto_test_last_run_at") or "").strip()
    runtime = get_runtime_status()
    next_run = runtime.get("autoTestNextRunAt") or ""
    if interval > 0 and not last_run and next_run == "pending":
        next_run = "即将执行"
    elif interval > 0 and last_run and next_run:
        pass
    return {
        "autoTestIntervalHours": interval,
        "autoTestEnabled": interval > 0,
        "autoTestLastRunAt": last_run,
        "autoTestNextRunAt": next_run,
        "autoTestRunning": bool(runtime.get("autoTestRunning")),
        "autoTestLastSummary": runtime.get("autoTestLastSummary") or "",
    }


def get_public_settings() -> dict[str, Any]:
    ensure_settings_ready()
    pool = get_proxy_pool()
    test_settings = get_test_settings()
    return {
        "hasCustomPassword": bool(get_setting("admin_password")),
        "proxyPoolText": "\n".join(pool),
        "proxyCount": len(pool),
        "defaultPasswordHint": "未设置自定义密码时，使用环境变量 ADMIN_PASSWORD 或默认 admin123",
        **test_settings,
        **get_auto_test_settings(),
    }


def update_settings(
    *,
    new_password: str | None = None,
    clear_password: bool = False,
    proxy_pool_text: str | None = None,
    test_models_text: str | None = None,
    default_test_model: str | None = None,
    default_test_message: str | None = None,
    auto_test_interval_hours: int | None = None,
    public_base_url: str | None = None,
) -> dict[str, Any]:
    ensure_settings_ready()
    with LOCK:
        if clear_password:
            delete_setting("admin_password")
        elif new_password is not None:
            password = new_password.strip()
            if not password:
                raise ValueError("登录密码不能为空")
            if len(password) < 6:
                raise ValueError("登录密码至少 6 位")
            set_setting("admin_password", _hash_admin_password(password))

        if proxy_pool_text is not None:
            set_setting_json("proxy_pool", parse_proxy_pool_text(proxy_pool_text))
            try:
                from core.card_store import backfill_empty_account_proxies

                backfill_empty_account_proxies()
            except Exception:
                pass

        if test_models_text is not None:
            models = parse_test_models_text(test_models_text)
            if not models:
                raise ValueError("请至少配置一个测试模型")
            set_setting_json("test_models", models)

        if default_test_model is not None:
            model = default_test_model.strip()
            if not model:
                raise ValueError("默认测试模型不能为空")
            set_setting("default_test_model", model)

        if default_test_message is not None:
            message = default_test_message.strip()
            if not message:
                raise ValueError("默认测试消息不能为空")
            set_setting("default_test_message", message)

        if auto_test_interval_hours is not None:
            from core.auto_test_scheduler import normalize_auto_test_interval

            interval = normalize_auto_test_interval(auto_test_interval_hours)
            set_setting("auto_test_interval_hours", str(interval))

        if public_base_url is not None:
            from core.api_gateway import set_configured_public_base_url

            set_configured_public_base_url(public_base_url)

    apply_runtime_settings()
    settings = get_public_settings()
    models = settings.get("models") or []
    default_model = settings.get("defaultModel") or DEFAULT_TEST_MODEL
    if default_model not in models:
        raise ValueError("默认测试模型必须在模型列表中")
    return settings
