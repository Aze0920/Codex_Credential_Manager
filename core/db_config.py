# -*- coding: utf-8 -*-
"""数据库路径与备份（当前仅 SQLite；MySQL 见 docs/DATABASE.md）。"""
from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def get_database_path() -> Path:
    """SQLite 文件路径。可通过环境变量 DATABASE_PATH 或 SQLITE_PATH 覆盖。"""
    override = (os.environ.get("DATABASE_PATH") or os.environ.get("SQLITE_PATH") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return PROJECT_ROOT / "data" / "card_system.db"


def get_backup_dir() -> Path:
    path = PROJECT_ROOT / "data" / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_database_backup(*, prefix: str = "card_system") -> Path:
    src = get_database_path()
    if not src.is_file():
        raise FileNotFoundError(f"数据库文件不存在: {src}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = get_backup_dir() / f"{prefix}-{stamp}.db"
    shutil.copy2(src, dest)
    return dest


def list_database_backups(*, limit: int = 20) -> list[dict[str, str | int]]:
    items: list[dict[str, str | int]] = []
    for path in sorted(get_backup_dir().glob("*.db"), reverse=True)[:limit]:
        stat = path.stat()
        items.append(
            {
                "name": path.name,
                "path": str(path),
                "size": stat.st_size,
                "modifiedAt": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return items
