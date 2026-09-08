"""数据库访问层 - 用 SQLAlchemy Core, 不引入 ORM (保持轻量)。"""
from __future__ import annotations
from datetime import datetime
from typing import Any
import json

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import settings


_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.db_url, pool_size=5, pool_recycle=3600, future=True)
    return _engine


def fetch_due_reports(now: datetime, limit: int = 100) -> list[dict]:
    """拉取下次执行时间 <= now 的活动报表。"""
    sql = text("""
        SELECT report_id, tenant_id, user_id, name, dsl_json, render_blocks,
               chart_spec, schedule_type, cron_expr, timezone, next_run_at,
               recipients, channels, push_silent_if_empty, push_format,
               effective_to, max_run_count, cost_owner_user_id, fail_count
        FROM scheduled_report
        WHERE status = 'ACTIVE'
          AND (next_run_at IS NULL OR next_run_at <= :now)
          AND (effective_to IS NULL OR effective_to >= :today)
        ORDER BY next_run_at ASC
        LIMIT :lim
    """)
    with get_engine().begin() as conn:
        rows = conn.execute(sql, {"now": now, "today": now.date(), "lim": limit}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        for k in ("dsl_json", "render_blocks", "chart_spec", "recipients", "channels"):
            v = d.get(k)
            if isinstance(v, str):
                try:
                    d[k] = json.loads(v)
                except Exception:
                    pass
        out.append(d)
    return out


def insert_run(report_id: int, tenant_id: int, scheduled_at: datetime,
               status: str = "PENDING") -> int:
    sql = text("""
        INSERT INTO scheduled_report_run (report_id, tenant_id, scheduled_at, status, started_at)
        VALUES (:rid, :tid, :sched, :st, NOW())
    """)
    with get_engine().begin() as conn:
        r = conn.execute(sql, {"rid": report_id, "tid": tenant_id, "sched": scheduled_at, "st": status})
        return r.lastrowid


def update_run(run_id: int, **fields) -> None:
    if not fields:
        return
    # JSON 字段序列化
    for k in ("blocks_json", "push_results"):
        if k in fields and not isinstance(fields[k], str):
            fields[k] = json.dumps(fields[k], ensure_ascii=False, default=str)
    set_clause = ", ".join(f"{k} = :{k}" for k in fields.keys())
    sql = text(f"UPDATE scheduled_report_run SET {set_clause} WHERE run_id = :run_id")
    with get_engine().begin() as conn:
        conn.execute(sql, {**fields, "run_id": run_id})


def update_report_next_run(report_id: int, next_run_at: datetime | None,
                            last_run_at: datetime | None, fail_count: int) -> None:
    sql = text("""
        UPDATE scheduled_report
        SET next_run_at = :next, last_run_at = :last, fail_count = :fc,
            status = CASE WHEN :fc >= :max_fail THEN 'PAUSED' ELSE status END
        WHERE report_id = :rid
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {
            "rid": report_id, "next": next_run_at, "last": last_run_at,
            "fc": fail_count, "max_fail": settings.max_fail_count,
        })


def write_chat_message(tenant_id: int, user_id: int, session_id: str,
                       blocks: list, summary: str, report_id: int) -> str:
    """把定时报表结果同步落到 chat_message, 让用户在聊天页能看到。"""
    import uuid
    msg_id = uuid.uuid4().hex
    sql = text("""
        INSERT INTO chat_message
          (message_id, session_id, tenant_id, user_id, role, content_text,
           blocks_json, status, created_at)
        VALUES
          (:mid, :sid, :tid, :uid, 'assistant', :txt, :blocks, 'DONE', NOW())
    """)
    with get_engine().begin() as conn:
        conn.execute(sql, {
            "mid": msg_id, "sid": session_id, "tid": tenant_id, "uid": user_id,
            "txt": summary, "blocks": json.dumps(blocks, ensure_ascii=False, default=str),
        })
    return msg_id


def get_report_subscribers(report_id: int) -> list[dict]:
    sql = text("""
        SELECT subscriber_user_id, channels, status
        FROM scheduled_report_subscription
        WHERE report_id = :rid AND status = 'ACTIVE'
    """)
    with get_engine().begin() as conn:
        rows = conn.execute(sql, {"rid": report_id}).mappings().all()
    out = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("channels"), str):
            try:
                d["channels"] = json.loads(d["channels"])
            except Exception:
                pass
        out.append(d)
    return out
