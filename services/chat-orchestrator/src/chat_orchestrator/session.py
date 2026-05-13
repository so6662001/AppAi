"""聊天会话/消息持久化 - 写 MySQL steel_chat.chat_session / chat_message."""
from __future__ import annotations
import json
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import settings


log = logging.getLogger("chat.session")
_engine: Engine | None = None


def get_db() -> Engine:
    global _engine
    if _engine is None:
        db_url = (settings.db_url if hasattr(settings, "db_url") else
                  "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4")
        _engine = create_engine(db_url, pool_pre_ping=True, pool_recycle=3600, future=True)
    return _engine


def new_session_id() -> str:
    return uuid.uuid4().hex


def ensure_session(session_id: str, tenant_id: int, user_id: int,
                   business_line: str | None = None, role: str | None = None,
                   title: str | None = None) -> str:
    """会话不存在则创建; 返回 session_id."""
    try:
        with get_db().begin() as conn:
            row = conn.execute(text(
                "SELECT session_id FROM chat_session WHERE session_id=:sid"
            ), {"sid": session_id}).first()
            if not row:
                conn.execute(text("""
                    INSERT INTO chat_session
                        (session_id, tenant_id, user_id, title, business_line, role, last_message_at)
                    VALUES (:sid, :tid, :uid, :ttl, :bl, :ro, NOW())
                """), {"sid": session_id, "tid": tenant_id, "uid": user_id,
                       "ttl": title or "新对话", "bl": business_line, "ro": role})
        return session_id
    except Exception as e:
        log.warning("ensure_session failed (ignored): %s", e)
        return session_id


def save_user_message(session_id: str, tenant_id: int, user_id: int, text_: str) -> str:
    msg_id = uuid.uuid4().hex
    try:
        with get_db().begin() as conn:
            conn.execute(text("""
                INSERT INTO chat_message
                    (message_id, session_id, tenant_id, user_id, role, content_text, status)
                VALUES (:mid, :sid, :tid, :uid, 'user', :txt, 'DONE')
            """), {"mid": msg_id, "sid": session_id, "tid": tenant_id,
                   "uid": user_id, "txt": text_})
    except Exception as e:
        log.warning("save_user_message failed: %s", e)
    return msg_id


def save_assistant_message(session_id: str, tenant_id: int, msg_id: str,
                           blocks: list[dict], summary: str, dsl: dict,
                           sql_text: Optional[str], metrics_used: list[str],
                           usage: dict, model_name: str, parent_message_id: str | None = None):
    try:
        with get_db().begin() as conn:
            conn.execute(text("""
                INSERT INTO chat_message
                    (message_id, session_id, tenant_id, role, content_text,
                     blocks_json, dsl_json, sql_text, metrics_used,
                     usage_input_tokens, usage_output_tokens, usage_biz_tokens,
                     usage_cost_cny, usage_bucket, model_name, cache_hit,
                     status, parent_message_id)
                VALUES (:mid, :sid, :tid, 'assistant', :txt,
                     :blocks, :dsl, :sql, :metrics,
                     :inp, :out, :biz, :cny, :bk, :model, :ch,
                     'DONE', :pm)
            """), {
                "mid": msg_id, "sid": session_id, "tid": tenant_id,
                "txt": summary,
                "blocks": json.dumps(blocks, ensure_ascii=False, default=str),
                "dsl":    json.dumps(dsl,    ensure_ascii=False, default=str),
                "sql": sql_text,
                "metrics": json.dumps(metrics_used, ensure_ascii=False),
                "inp": usage.get("inputTokens"),
                "out": usage.get("outputTokens"),
                "biz": usage.get("bizTokensCharged"),
                "cny": usage.get("costCny"),
                "bk":  usage.get("bucket"),
                "model": model_name, "ch": 1 if usage.get("cacheHit") else 0,
                "pm": parent_message_id,
            })
            conn.execute(text(
                "UPDATE chat_session SET last_message_at=NOW() WHERE session_id=:sid"
            ), {"sid": session_id})
    except Exception as e:
        log.warning("save_assistant_message failed: %s", e)


def list_sessions(tenant_id: int, user_id: int, limit: int = 30) -> list[dict]:
    try:
        with get_db().begin() as conn:
            rows = conn.execute(text("""
                SELECT session_id, title, business_line, role, pinned,
                       created_at, updated_at, last_message_at
                FROM chat_session
                WHERE tenant_id=:tid AND user_id=:uid AND is_deleted=0
                ORDER BY COALESCE(last_message_at, created_at) DESC
                LIMIT :lim
            """), {"tid": tenant_id, "uid": user_id, "lim": limit}).mappings().all()
        return [dict(r) for r in rows]
    except Exception:
        return []


def get_messages(session_id: str, tenant_id: int, limit: int = 100) -> list[dict]:
    try:
        with get_db().begin() as conn:
            rows = conn.execute(text("""
                SELECT message_id, role, content_text, blocks_json, dsl_json,
                       usage_biz_tokens, model_name, created_at
                FROM chat_message
                WHERE session_id=:sid AND tenant_id=:tid
                ORDER BY created_at ASC LIMIT :lim
            """), {"sid": session_id, "tid": tenant_id, "lim": limit}).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            for k in ("blocks_json", "dsl_json"):
                if isinstance(d.get(k), str):
                    try: d[k] = json.loads(d[k])
                    except Exception: pass
            out.append(d)
        return out
    except Exception:
        return []


def feedback(message_id: str, tenant_id: int, user_id: int,
             vote: str, reason: str | None = None, remark: str | None = None) -> bool:
    try:
        with get_db().begin() as conn:
            conn.execute(text("""
                INSERT INTO chat_feedback (message_id, tenant_id, user_id, vote, reason, remark)
                VALUES (:mid, :tid, :uid, :v, :rs, :rm)
            """), {"mid": message_id, "tid": tenant_id, "uid": user_id,
                   "v": vote, "rs": reason, "rm": remark})
        return True
    except Exception as e:
        log.warning("feedback failed: %s", e)
        return False
