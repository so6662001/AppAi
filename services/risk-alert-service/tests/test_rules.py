"""规则引擎 + 冷却 + 表达式测试."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from risk_alert.rules import evaluate, load_rules, AlertRule
from risk_alert import cooldown


# ============ 表达式 ============

def test_eval_greater():
    assert evaluate("value > 0.95", {"value": 0.97}) is True
    assert evaluate("value > 0.95", {"value": 0.50}) is False


def test_eval_less_equal():
    assert evaluate("value <= 100", {"value": 80}) is True
    assert evaluate("value <= 100", {"value": 200}) is False


def test_eval_reference_constant():
    assert evaluate("value > hedge_limit", {"value": 1.5, "hedge_limit": 1.0}) is True


def test_eval_no_variable():
    assert evaluate("value > 0.5", {}) is False


def test_eval_empty():
    assert evaluate("", {"value": 1}) is False


# ============ 规则加载 ============

def test_load_rules_from_metrics_dir():
    metrics_dir = Path("/workspace/metrics")
    rules = load_rules(metrics_dir)
    assert len(rules) >= 4
    ids = {r.id for r in rules}
    assert "ALERT_CREDIT_OVER" in ids
    assert "ALERT_HEDGE_BREACH" in ids


def test_load_rule_fields():
    metrics_dir = Path("/workspace/metrics")
    rules = load_rules(metrics_dir)
    r = next(r for r in rules if r.id == "ALERT_CREDIT_OVER")
    assert r.metric == "credit_utilization_rate"
    assert r.severity == "HIGH"
    assert r.cooldown_hours == 12


# ============ 冷却 ============

class _FakeRedis:
    def __init__(self): self.store = {}
    def set(self, k, v, ex=None, nx=False):
        if nx and k in self.store: return False
        self.store[k] = v
        return True


def test_cooldown_acquire_release():
    with patch.object(cooldown, 'client', return_value=_FakeRedis()):
        ok1 = cooldown.try_acquire(1, "RULE_X", "metric_a", 12)
        ok2 = cooldown.try_acquire(1, "RULE_X", "metric_a", 12)
    assert ok1 is True
    assert ok2 is False


def test_cooldown_different_entity():
    with patch.object(cooldown, 'client', return_value=_FakeRedis()):
        ok1 = cooldown.try_acquire(1, "RULE_X", "metric_a", 12)
        ok2 = cooldown.try_acquire(1, "RULE_X", "metric_b", 12)
    assert ok1 and ok2          # entity 不同, 都允许


def test_cooldown_redis_down_returns_true():
    bad = MagicMock()
    bad.set.side_effect = ConnectionError("redis down")
    with patch.object(cooldown, 'client', return_value=bad):
        ok = cooldown.try_acquire(1, "RULE_X", "metric_a", 12)
    assert ok is True   # 降级允许通过, 避免漏告警
