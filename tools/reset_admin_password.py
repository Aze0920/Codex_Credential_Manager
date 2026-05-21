# -*- coding: utf-8 -*-
"""重置后台登录密码为默认（admin123 或环境变量 ADMIN_PASSWORD）。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.app_settings import _default_admin_password, reset_admin_password_to_default


def main() -> int:
    reset_admin_password_to_default()
    default_password = _default_admin_password()
    print("已清除自定义后台密码。")
    print(f"请使用默认密码登录：{default_password}")
    if default_password == "admin123":
        print("（若设置了环境变量 ADMIN_PASSWORD，以环境变量为准）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
