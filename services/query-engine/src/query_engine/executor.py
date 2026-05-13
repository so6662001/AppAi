"""SQL 执行 + 审计 + 缓存."""
from __future__ import annotations
import json
import logging
import os
import time
from typing import Any

from . import cache


log = logging.getLogger("query.exec")


def execute(sql: str, params: dict, tenant_id: int, user_id: int,
            no_cache: bool = False, row_limit: int = 50000) -> dict:
    """返回 {rows, exec_ms, cache_hit, sql_hash, scan_rows}.
    SQL 已由上游 DSL 编译器加固 (LIMIT/参数化/只读账号)."""

    sql_hash = cache.hash_sql(sql, params)
    if not no_cache:
        cached = cache.get(sql_hash)
        if cached is not None:
            return {"rows": cached, "exec_ms": 0, "cache_hit": True,
                    "sql_hash": sql_hash, "scan_rows": len(cached)}

    t0 = time.time()
    rows = _execute_sr(sql, params)
    exec_ms = int((time.time() - t0) * 1000)
    if len(rows) > row_limit:
        rows = rows[:row_limit]

    # 写缓存
    if rows and not no_cache:
        cache.set_(sql_hash, rows, ttl_sec=300)

    # 写审计 (异步, 失败不阻塞)
    try:
        _write_audit(tenant_id, user_id, sql, sql_hash, exec_ms, len(rows))
    except Exception:
        pass

    return {"rows": rows, "exec_ms": exec_ms, "cache_hit": False,
            "sql_hash": sql_hash, "scan_rows": len(rows)}


def _execute_sr(sql: str, params: dict) -> list[dict]:
    try:
        import pymysql
        host = os.environ.get("SR_HOST", "localhost")
        port = int(os.environ.get("SR_PORT", 9030))
        user = os.environ.get("SR_USER", "root")
        pwd = os.environ.get("SR_PASS", "")
        db = os.environ.get("SR_DB", "steel_dw")
        safe = sql
        for k in params: safe = safe.replace(f":{k}", f"%({k})s")
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd, db=db,
                               charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
                               connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(safe, params)
                return list(cur.fetchall())
        finally:
            conn.close()
    except Exception as e:
        log.warning("SR exec failed (return empty): %s", e)
        return []


def _write_audit(tenant_id: int, user_id: int, sql: str, sql_hash: str,
                 exec_ms: int, scan_rows: int):
    """异步写 query_audit_log. 真实环境通过 Kafka 异步, 这里同步 try-best."""
    try:
        import pymysql
        host = os.environ.get("MYSQL_HOST", "localhost")
        port = int(os.environ.get("MYSQL_PORT", 3306))
        user = os.environ.get("MYSQL_USER", "root")
        pwd = os.environ.get("MYSQL_PASS", "steeldev")
        conn = pymysql.connect(host=host, port=port, user=user, password=pwd,
                               db="steel_governance", charset="utf8mb4",
                               connect_timeout=2)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO query_audit_log (tenant_id, user_id, sql_text, exec_ms, "
                    "scan_rows, cache_hit) VALUES (%s,%s,%s,%s,%s,0)",
                    (tenant_id, user_id, sql[:1000], exec_ms, scan_rows))
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
