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


# ============ L2: 问题向量相似度缓存 ============
# 思路:
#   - 把 (question_text, dsl) 嵌入向量, 存 redis hash
#   - 命中: 找余弦相似度 >= 0.92 的过往问题, 直接复用 SQL hash 的缓存结果
#   - 既能命中"上周华东销售额"和"上周华东销售总额"这种语义同义问题

import math


def _embed(text: str, dim: int = 256) -> list[float]:
    """与 rag-service 用同一份算法(简化 BoW), 测试时无依赖."""
    import re
    vec = [0.0] * dim
    for t in re.split(r"[\s,.;!?，。；！？\-:：()（）]+", text or ""):
        if t:
            vec[hash(t) % dim] += 1.0
    n = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x / n for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x*y for x, y in zip(a, b))


def l2_lookup(question: str, sim_threshold: float = 0.92) -> tuple[str, list[dict]] | None:
    """L2: 找语义相似的过往问题, 返回 (sql_hash, rows) 或 None."""
    r = _redis()
    if not r or not question: return None
    qv = _embed(question)
    try:
        # 用 SCAN 替代 KEYS, 避免阻塞 Redis
        for key in r.scan_iter(match="q2:*", count=200):
            raw = r.get(key)
            if not raw: continue
            try:
                entry = json.loads(raw)
                v = entry.get("vec")
                if not v: continue
                sim = _cosine(qv, v)
                if sim >= sim_threshold:
                    cached_rows = get(entry["sql_hash"])
                    if cached_rows is not None:
                        log.info("L2 cache hit sim=%.3f", sim)
                        return entry["sql_hash"], cached_rows
            except Exception:
                continue
    except Exception:
        pass
    return None


def l2_record(question: str, sql_hash: str, ttl_sec: int = 1800):
    """把 (question, sql_hash) 关联存入 L2 表."""
    r = _redis()
    if not r or not question: return
    try:
        key = "q2:" + hashlib.sha256(question.encode()).hexdigest()[:16]
        r.set(key, json.dumps({
            "question": question, "sql_hash": sql_hash,
            "vec": _embed(question),
        }, ensure_ascii=False), ex=ttl_sec)
    except Exception:
        pass
