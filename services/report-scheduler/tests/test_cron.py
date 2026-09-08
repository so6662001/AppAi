"""测试 cron 解析与执行计划。"""
from __future__ import annotations
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from report_scheduler.cron import next_run_at


def test_daily_default():
    """schedule_type=daily 默认每天 8:00。"""
    base = datetime(2026, 5, 13, 12, 0)
    nxt = next_run_at(None, "daily", base, "Asia/Shanghai")
    assert nxt is not None
    assert nxt.hour == 8


def test_weekly_default():
    base = datetime(2026, 5, 13, 12, 0)   # 周三
    nxt = next_run_at(None, "weekly", base, "Asia/Shanghai")
    assert nxt is not None
    assert nxt.weekday() == 0             # 下次周一


def test_cron_8am():
    """每天 8 点。"""
    base = datetime(2026, 5, 13, 7, 0)
    nxt = next_run_at("0 0 8 * * ?", "cron", base, "Asia/Shanghai")
    assert nxt.hour == 8 and nxt.day == 13


def test_cron_monday_8am():
    """每周一 8 点 -- 6 段 cron。"""
    base = datetime(2026, 5, 13, 9, 0)   # 周三 9 点
    nxt = next_run_at("0 0 8 ? * MON", "cron", base, "Asia/Shanghai")
    assert nxt.weekday() == 0
    assert nxt.hour == 8


def test_monthly_first_day():
    base = datetime(2026, 5, 13, 12, 0)
    nxt = next_run_at("0 0 9 1 * ?", "cron", base, "Asia/Shanghai")
    assert nxt.day == 1 and nxt.hour == 9
    assert nxt.month == 6                # 下一个月 1 号


def test_once_returns_none():
    base = datetime(2026, 5, 13, 8, 0)
    nxt = next_run_at(None, "once", base, "Asia/Shanghai")
    assert nxt is None
