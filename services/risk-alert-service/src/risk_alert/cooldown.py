"""规则冷却(Redis SETNX + TTL): 同一 tenant+rule+entity 在冷却期内只发一次."""
from __future__ import annotations
import redis
from .config import settings


_client: redis.Redis | None = None


def client() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(host=settings.redis_host, port=settings.redis_port,
                              decode_responses=True, socket_connect_timeout=2)
    return _client


def try_acquire(tenant_id: int, rule_id: str, entity_key: str, cooldown_hours: int) -> bool:
    """尝试占冷却锁. 返回 True 表示可推送, False 表示冷却中."""
    key = f"alert:cooldown:{tenant_id}:{rule_id}:{entity_key}"
    try:
        ok = client().set(key, "1", ex=max(60, cooldown_hours * 3600), nx=True)
        return bool(ok)
    except Exception:
        # Redis 不可达时降级为"始终允许", 避免漏告警
        return True
