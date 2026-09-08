"""query-engine 错误传递测试 - 区分 empty vs failed."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from query_engine import executor


def test_db_unreachable_returns_error_status():
    """DB 不可达时 status=FAILED, 不再静默返回空列表."""
    r = executor.execute("SELECT 1", {}, 1, 1, no_cache=True)
    # DB 不可达 → 返回 FAILED 状态
    assert r.get("status") == "FAILED"
    assert "error" in r
    assert r["rows"] == []


def test_execute_with_question_records_l2_when_success(monkeypatch):
    """成功执行 + 带 question, 应同时写 L1 + L2."""
    import fakeredis
    from query_engine import cache as cache_mod
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache_mod, "_redis", lambda: fake)

    # mock _execute_sr_safe 返回成功
    monkeypatch.setattr(executor, "_execute_sr_safe",
                        lambda sql, params: ([{"x": 1}], None))
    r = executor.execute("SELECT 1", {}, 1, 1, question="我的销售额")
    assert r.get("status") != "FAILED"
    assert r["cache_hit"] is False
    # L2 应有记录
    l2_keys = list(fake.scan_iter(match="q2:*"))
    assert len(l2_keys) == 1
