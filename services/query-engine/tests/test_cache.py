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
