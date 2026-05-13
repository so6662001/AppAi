"""DQ check 单元测试."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dq_monitor import checks


def test_freshness_pass():
    r = checks.check_freshness("M001", datetime.utcnow() - timedelta(minutes=10), sla_minutes=60)
    assert r.passed and r.severity == "LOW"


def test_freshness_fail():
    r = checks.check_freshness("M001", datetime.utcnow() - timedelta(minutes=120), sla_minutes=60)
    assert not r.passed and r.severity == "HIGH"


def test_null_ratio_pass():
    r = checks.check_null_ratio("M001", 2, 100, threshold=0.05)
    assert r.passed


def test_null_ratio_fail():
    r = checks.check_null_ratio("M001", 12, 100, threshold=0.05)
    assert not r.passed
    assert r.detail["actual"] == 0.12


def test_spike_fail():
    r = checks.check_spike("M001", current_value=200, baseline=100, threshold_pct=0.5)
    assert not r.passed


def test_spike_pass_low_delta():
    r = checks.check_spike("M001", current_value=105, baseline=100, threshold_pct=0.1)
    assert r.passed


def test_consistency():
    assert checks.check_consistency("M001", 1000, 1000.0001).passed
    assert not checks.check_consistency("M001", 1000, 900).passed
