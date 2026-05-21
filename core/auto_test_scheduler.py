# -*- coding: utf-8 -*-
"""账号池定时自动测试（登录 + 额度 + 默认模型对话）。"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from core.activity_logger import log_activity, log_exception
from core.card_store import get_setting, list_auto_test_account_ids, now_iso, set_setting, test_pool_account

CHECK_INTERVAL_SECONDS = 60
_cycle_lock = threading.Lock()
_cycle_running = False
_scheduler_thread: threading.Thread | None = None
_scheduler_stop = threading.Event()
_scheduler_lock = threading.Lock()
_last_summary: dict[str, Any] = {}


def normalize_auto_test_interval(value: Any) -> int:
    try:
        hours = int(value)
    except (TypeError, ValueError):
        hours = 0
    return max(0, min(24, hours))


def get_auto_test_interval_hours() -> int:
    return normalize_auto_test_interval(get_setting("auto_test_interval_hours") or "0")


def _parse_iso(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def should_run_auto_test(*, interval_hours: int | None = None, last_run_at: str | None = None) -> bool:
    interval = normalize_auto_test_interval(interval_hours if interval_hours is not None else get_auto_test_interval_hours())
    if interval <= 0:
        return False
    last_run = (last_run_at if last_run_at is not None else (get_setting("auto_test_last_run_at") or "")).strip()
    if not last_run:
        return True
    last_dt = _parse_iso(last_run)
    if not last_dt:
        return True
    return datetime.now() >= last_dt + timedelta(hours=interval)


def get_runtime_status() -> dict[str, Any]:
    interval = get_auto_test_interval_hours()
    last_run = (get_setting("auto_test_last_run_at") or "").strip()
    next_run = ""
    if interval > 0:
        if not last_run:
            next_run = "pending"
        else:
            last_dt = _parse_iso(last_run)
            if last_dt:
                next_run = (last_dt + timedelta(hours=interval)).isoformat(timespec="seconds")
    summary_text = ""
    if _last_summary:
        summary_text = (
            f"成功 {_last_summary.get('success', 0)} / 失败 {_last_summary.get('failed', 0)} / "
            f"共 {_last_summary.get('total', 0)}"
        )
    stored_summary = get_setting("auto_test_last_summary") or ""
    if not summary_text and stored_summary:
        try:
            parsed = json.loads(stored_summary)
            if isinstance(parsed, dict):
                summary_text = (
                    f"成功 {parsed.get('success', 0)} / 失败 {parsed.get('failed', 0)} / "
                    f"共 {parsed.get('total', 0)}"
                )
        except json.JSONDecodeError:
            summary_text = stored_summary
    return {
        "autoTestRunning": _cycle_running,
        "autoTestLastSummary": summary_text,
        "autoTestNextRunAt": next_run,
    }


def run_auto_test_cycle(*, trigger: str = "schedule") -> dict[str, Any]:
    global _last_summary
    if not _cycle_lock.acquire(blocking=False):
        return {"ok": False, "skipped": True, "reason": "已有自动测试任务在运行"}
    _cycle_running = True
    started_at = now_iso()
    success = 0
    failed = 0
    account_ids = list_auto_test_account_ids()
    total = len(account_ids)
    try:
        log_activity(
            category="test",
            action="auto_test.start",
            message=f"开始自动测试，共 {total} 个账号",
            status="running",
            detail={"trigger": trigger, "total": total},
        )
        for index, account_id in enumerate(account_ids, start=1):
            if get_auto_test_interval_hours() <= 0 and trigger == "schedule":
                break
            try:
                result = test_pool_account(account_id, source="auto")
                if str(result.get("testStatus") or "").strip().lower() == "success":
                    success += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                log_exception(
                    category="test",
                    action="auto_test.account",
                    message=f"自动测试失败 ({index}/{total})",
                    exc=exc,
                    account_id=account_id,
                )
        finished_at = now_iso()
        summary = {
            "ok": True,
            "trigger": trigger,
            "startedAt": started_at,
            "finishedAt": finished_at,
            "total": total,
            "success": success,
            "failed": failed,
        }
        _last_summary = summary
        set_setting("auto_test_last_run_at", finished_at)
        set_setting("auto_test_last_summary", json.dumps(summary, ensure_ascii=False))
        log_activity(
            category="test",
            action="auto_test.done",
            message=f"自动测试完成：成功 {success}，失败 {failed}，共 {total}",
            status="success" if failed == 0 else "failed",
            detail=summary,
        )
        return summary
    except Exception as exc:
        log_exception(category="test", action="auto_test.failed", message="自动测试批次失败", exc=exc)
        raise
    finally:
        _cycle_running = False
        _cycle_lock.release()


def _scheduler_loop() -> None:
    while not _scheduler_stop.is_set():
        try:
            if should_run_auto_test() and not _cycle_running:
                threading.Thread(
                    target=run_auto_test_cycle,
                    kwargs={"trigger": "schedule"},
                    daemon=True,
                    name="auto-test-cycle",
                ).start()
        except Exception as exc:
            log_exception(category="test", action="auto_test.scheduler", message="自动测试调度异常", exc=exc)
        _scheduler_stop.wait(CHECK_INTERVAL_SECONDS)


def start_auto_test_scheduler() -> None:
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        _scheduler_stop.clear()
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            daemon=True,
            name="auto-test-scheduler",
        )
        _scheduler_thread.start()
