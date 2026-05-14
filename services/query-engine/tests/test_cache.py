"""缓存逻辑测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from query_engine import cache


def test_hash_deterministic():
    h1 = cache.hash_sql("SELECT 1", {"a": 1, "b": 2})
    h2 = cache.hash_sql("SELECT 1", {"b": 2, "a": 1})
    assert h1 == h2


def test_hash_different_for_different_sql():
    assert cache.hash_sql("SELECT 1", {}) != cache.hash_sql("SELECT 2", {})


def test_get_returns_none_when_redis_down(monkeypatch):
    monkeypatch.setattr(cache, "_redis", lambda: None)
    assert cache.get("anyhash") is None


def test_set_get_via_fakeredis(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", lambda: fake)
    cache.set_("h1", [{"a": 1}, {"b": 2}], ttl_sec=60)
    out = cache.get("h1")
    assert out == [{"a": 1}, {"b": 2}]


def test_executor_returns_empty_when_sr_down():
    from query_engine import executor
    r = executor.execute("SELECT 1", {}, 1, 1, no_cache=True)
    assert "rows" in r and "exec_ms" in r
    assert r["cache_hit"] is False


def test_l2_cache_record_and_lookup(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", lambda: fake)
    # 先 set L1
    cache.set_("hash1", [{"a": 1}], ttl_sec=60)
    # 关联记录 L2
    cache.l2_record("上周华东销售额", "hash1")
    # 语义相似的问题应该命中
    hit = cache.l2_lookup("上周华东销售额")
    assert hit and hit[0] == "hash1"


def test_l2_cache_no_match_for_unrelated(monkeypatch):
    import fakeredis
    fake = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_redis", lambda: fake)
    cache.set_("hash1", [{"a": 1}], ttl_sec=60)
    cache.l2_record("上周华东销售额", "hash1")
    hit = cache.l2_lookup("生产线 OEE 故障", sim_threshold=0.92)
    assert hit is None
