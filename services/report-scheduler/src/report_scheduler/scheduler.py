"""调度器主循环 - APScheduler 周期扫描 + 立即触发。"""
from __future__ import annotations
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .db import fetch_due_reports
from .executor import execute_report


log = logging.getLogger("scheduler.main")
_thread_pool = ThreadPoolExecutor(max_workers=settings.max_concurrent_jobs,
                                  thread_name_prefix="report-exec")
_scheduler = BackgroundScheduler(timezone=settings.tz)


def scan_and_dispatch():
    """每 scan_interval_seconds 跑一次, 拉 due 报表分发到线程池。"""
    now = datetime.utcnow()
    due = fetch_due_reports(now=now, limit=settings.max_concurrent_jobs * 5)
    if not due:
        return
    log.info("scan dispatched %s reports", len(due))
    for r in due:
        _thread_pool.submit(execute_report, r)


def start() -> None:
    _scheduler.add_job(
        scan_and_dispatch,
        trigger=IntervalTrigger(seconds=settings.scan_interval_seconds),
        id="report_scan",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    _scheduler.start()
    log.info("scheduler started, scan_interval=%ss", settings.scan_interval_seconds)


def stop() -> None:
    _scheduler.shutdown(wait=False)
    _thread_pool.shutdown(wait=False)


def run_one_now(report: dict) -> None:
    _thread_pool.submit(execute_report, report)
