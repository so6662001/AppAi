"""L1 + L2 缓存.

L1: 完全相同 (sql_hash) → 直接返回结果. TTL = 5 分钟 (按数据更新策略可调)
L2: 相同 sql_hash 但 cache_meta 不同 → 部分命中, 留作扩展
L3: 物化视图 路由由 DSL 编译器负责, 不在本层
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
from typing import Optional

import redis

log = logging.getLogger("query.cache")


_client: redis.Redis | None = None


def _redis() -> redis.Redis | None:
    global _client
    if _client is None:
        try:
            _client = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"),
                                  port=int(os.environ.get("REDIS_PORT", 6379)),
                                  decode_responses=True, socket_connect_timeout=2)
            _client.ping()
        except Exception as e:
            log.warning("Redis unavailable, cache disabled: %s", e)
            _client = None
    return _client


def hash_sql(sql: str, params: dict) -> str:
    raw = sql + "|" + json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def get(sql_hash: str) -> list[dict] | None:
    r = _redis()
    if not r: return None
    try:
        raw = r.get("q:" + sql_hash)
        if raw is None: return None
        return json.loads(raw)
    except Exception:
        return None


def set_(sql_hash: str, rows: list[dict], ttl_sec: int = 300):
    r = _redis()
    if not r: return
    try:
        r.set("q:" + sql_hash, json.dumps(rows, ensure_ascii=False, default=str),
              ex=ttl_sec)
    except Exception:
        pass


def invalidate_prefix(prefix: str = ""):
    r = _redis()
    if not r: return
    try:
        for k in r.scan_iter(match=f"q:{prefix}*"):
            r.delete(k)
    except Exception:
        pass
