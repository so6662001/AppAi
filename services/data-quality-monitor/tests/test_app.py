"""DQ app scan + fact 白名单测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dq_monitor.app import _is_valid_fact_table, _scan


def test_valid_fact_names():
    assert _is_valid_fact_table("dws_sales_daily")
    assert _is_valid_fact_table("dwd_inv_balance")
    assert _is_valid_fact_table("ads_revenue")
    assert _is_valid_fact_table("dim_customer_his")


def test_invalid_fact_names_rejected():
    # 防止 SQL 标识符注入
    assert not _is_valid_fact_table("users; DROP TABLE x")
    assert not _is_valid_fact_table("DBA.users")
    assert not _is_valid_fact_table("./../passwd")
    assert not _is_valid_fact_table("foo")
    assert not _is_valid_fact_table("dws_")
    assert not _is_valid_fact_table("")
    assert not _is_valid_fact_table(None)


def test_scan_does_not_throw_when_db_unavailable():
    """DB 不可达时 _scan 应优雅返回不抛."""
    _scan()
