"""从 MySQL tenant_notify_config 表查询各租户的通知渠道配置。

带 30s 进程内缓存, 避免每次推送都查表。
"""
from __future__ import annotations
import json
import time
import logging
from typing import Any
from sqlalchemy import text

from .db import get_engine


log = logging.getLogger("scheduler.tenant_config")


_CACHE: dict[tuple[int, str], tuple[dict, float]] = {}
_CACHE_TTL_SEC = 30.0


def get_config(tenant_id: int, channel: str) -> dict | None:
    """获取该租户该渠道的默认 config_json. 不存在返回 None."""
    key = (tenant_id, channel)
    now = time.time()
    if key in _CACHE:
        v, t = _CACHE[key]
        if now - t < _CACHE_TTL_SEC:
            return v

    sql = text("""
        SELECT config_json FROM tenant_notify_config
        WHERE tenant_id = :tid AND channel = :ch AND is_active = 1
        ORDER BY is_default DESC, config_id ASC
        LIMIT 1
    """)
    with get_engine().begin() as conn:
        row = conn.execute(sql, {"tid": tenant_id, "ch": channel}).first()
    if not row:
        _CACHE[key] = (None, now)
        return None
    cfg_raw = row[0]
    cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
    _CACHE[key] = (cfg, now)
    return cfg


def invalidate(tenant_id: int = None, channel: str = None) -> None:
    """让外部在配置变更后强制刷新。"""
    global _CACHE
    if tenant_id is None and channel is None:
        _CACHE = {}
        return
    keys = list(_CACHE.keys())
    for k in keys:
        if (tenant_id is None or k[0] == tenant_id) and (channel is None or k[1] == channel):
            del _CACHE[k]
