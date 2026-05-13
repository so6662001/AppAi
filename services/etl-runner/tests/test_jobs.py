"""验证 ETL 任务在 DB 不可达时不抛异常."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from etl_runner import jobs


def test_inv_daily_snapshot_returns_int_when_db_down():
    rc = jobs.inv_daily_snapshot()
    assert isinstance(rc, int)
    assert rc == 0      # DB 不可达时优雅返回 0


def test_jobs_registry_has_inv_snapshot():
    assert "inv_daily_snapshot" in jobs.JOBS
    assert callable(jobs.JOBS["inv_daily_snapshot"])


def test_dws_sales_daily_placeholder():
    rc = jobs.dws_sales_daily()
    assert rc == 0
