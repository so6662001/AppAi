"""advice engine 测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from advice import engine


def test_load_rules_from_metrics_yaml():
    # 应能加载 metrics_forecast.yaml 的 action_rules
    engine.METRICS_DIR = Path("/workspace/metrics")
    rules = engine.load_rules()
    assert len(rules) >= 4
    ids = {r.id for r in rules}
    assert "ACT_ACCELERATE_SHIPMENT" in ids


def test_evaluate_when_simple():
    ctx = {"forecast_index_price_nextweek": 4100, "listed_price": 4200,
           "daily_inv_tonnage": 1820, "avg_inv_tonnage": 1480}
    expr = "forecast_index_price_nextweek < listed_price * 0.98 AND daily_inv_tonnage > avg_inv_tonnage * 1.2"
    assert engine.evaluate_when(expr, ctx) is True


def test_evaluate_when_false():
    ctx = {"forecast_index_price_nextweek": 5000, "listed_price": 4200,
           "daily_inv_tonnage": 1820, "avg_inv_tonnage": 1480}
    expr = "forecast_index_price_nextweek < listed_price * 0.98 AND daily_inv_tonnage > avg_inv_tonnage * 1.2"
    assert engine.evaluate_when(expr, ctx) is False


def test_evaluate_when_unknown_var_returns_false():
    """缺少变量时安全返回 False, 不抛异常."""
    assert engine.evaluate_when("foo > 100", {}) is False


def test_evaluate_when_unsafe_input_blocked():
    """禁止任意代码注入."""
    assert engine.evaluate_when("__import__('os').system('rm -rf /')", {"a": 1}) is False
