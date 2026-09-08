"""briefing_card / briefing_layout / briefing_feedback CRUD."""
from __future__ import annotations
import json
import logging
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import settings


log = logging.getLogger("briefing.db")
_engine: Engine | None = None


def db() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(settings.db_url, pool_pre_ping=True, future=True)
    return _engine


def insert_card(tenant_id: int, user_id: int, biz_date: date,
                card_type: str, severity: str, rank_score: float,
                title: str, payload: dict, source_metrics: list[str],
                actions: list[dict]) -> int:
    sql = text("""
        INSERT INTO briefing_card (tenant_id, user_id, biz_date, card_type, severity,
            rank_score, title, payload_json, source_metrics, actions_json, status)
        VALUES (:tid, :uid, :bd, :ct, :sv, :rs, :ti, :pl, :sm, :ac, 'NEW')
    """)
    with db().begin() as conn:
        r = conn.execute(sql, {
            "tid": tenant_id, "uid": user_id, "bd": biz_date,
            "ct": card_type, "sv": severity, "rs": rank_score,
            "ti": title,
            "pl": json.dumps(payload, ensure_ascii=False, default=str),
            "sm": json.dumps(source_metrics, ensure_ascii=False),
            "ac": json.dumps(actions, ensure_ascii=False, default=str),
        })
        return r.lastrowid


def list_today(tenant_id: int, user_id: int, biz_date: date) -> list[dict]:
    try:
        with db().begin() as conn:
            rows = conn.execute(text("""
                SELECT card_id, card_type, severity, rank_score, title,
                       payload_json, source_metrics, actions_json, status,
                       expires_at, created_at
                FROM briefing_card
                WHERE tenant_id=:tid AND user_id=:uid AND biz_date=:bd
                ORDER BY rank_score DESC, card_id ASC
            """), {"tid": tenant_id, "uid": user_id, "bd": biz_date}).mappings().all()
        return [_decode(r) for r in rows]
    except Exception:
        return []


def _decode(r: dict) -> dict:
    d = dict(r)
    for k in ("payload_json", "source_metrics", "actions_json"):
        if isinstance(d.get(k), str):
            try: d[k] = json.loads(d[k])
            except Exception: pass
    return d


def list_history(tenant_id: int, user_id: int, from_d: date, to_d: date,
                 page: int = 1, size: int = 30) -> tuple[int, list[dict]]:
    try:
        with db().begin() as conn:
            total = conn.execute(text("""
                SELECT COUNT(DISTINCT biz_date) FROM briefing_card
                WHERE tenant_id=:tid AND user_id=:uid
                  AND biz_date BETWEEN :f AND :t
            """), {"tid": tenant_id, "uid": user_id, "f": from_d, "t": to_d}).scalar() or 0
            rows = conn.execute(text("""
                SELECT biz_date, COUNT(*) AS card_count FROM briefing_card
                WHERE tenant_id=:tid AND user_id=:uid
                  AND biz_date BETWEEN :f AND :t
                GROUP BY biz_date ORDER BY biz_date DESC
                LIMIT :lim OFFSET :off
            """), {"tid": tenant_id, "uid": user_id, "f": from_d, "t": to_d,
                   "lim": size, "off": (page - 1) * size}).mappings().all()
        return int(total), [dict(r) for r in rows]
    except Exception:
        return 0, []


def mark_read(card_id: int):
    try:
        with db().begin() as conn:
            conn.execute(text(
                "UPDATE briefing_card SET status='READ', read_at=NOW() WHERE card_id=:c"
            ), {"c": card_id})
    except Exception: pass


def mark_acted(card_id: int):
    try:
        with db().begin() as conn:
            conn.execute(text(
                "UPDATE briefing_card SET status='ACTED', acted_at=NOW() WHERE card_id=:c"
            ), {"c": card_id})
    except Exception: pass


def mark_ignored(card_id: int):
    try:
        with db().begin() as conn:
            conn.execute(text(
                "UPDATE briefing_card SET status='IGNORED' WHERE card_id=:c"
            ), {"c": card_id})
    except Exception: pass


def save_feedback(card_id: int, tenant_id: int, user_id: int,
                  vote: str, reason: str | None = None, remark: str | None = None) -> bool:
    try:
        with db().begin() as conn:
            conn.execute(text("""
                INSERT INTO briefing_feedback (card_id, tenant_id, user_id, vote, reason, remark)
                VALUES (:c, :tid, :uid, :v, :rs, :rm)
            """), {"c": card_id, "tid": tenant_id, "uid": user_id,
                   "v": vote, "rs": reason, "rm": remark})
        return True
    except Exception:
        return False


def get_layout(tenant_id: int, user_id: int) -> dict | None:
    try:
        with db().begin() as conn:
            r = conn.execute(text(
                "SELECT * FROM briefing_layout WHERE tenant_id=:t AND user_id=:u"
            ), {"t": tenant_id, "u": user_id}).mappings().first()
        if not r: return None
        d = dict(r)
        for k in ("cards", "kpi_metrics", "thresholds", "push_channels"):
            if isinstance(d.get(k), str):
                try: d[k] = json.loads(d[k])
                except Exception: pass
        return d
    except Exception:
        return None


def upsert_layout(tenant_id: int, user_id: int, payload: dict):
    try:
        with db().begin() as conn:
            conn.execute(text("""
                INSERT INTO briefing_layout (tenant_id, user_id, role, cards,
                    kpi_metrics, silence_from, silence_to, thresholds, push_channels)
                VALUES (:t,:u,:r,:c,:k,:sf,:st,:th,:pc)
                ON DUPLICATE KEY UPDATE
                    cards=VALUES(cards), kpi_metrics=VALUES(kpi_metrics),
                    silence_from=VALUES(silence_from), silence_to=VALUES(silence_to),
                    thresholds=VALUES(thresholds), push_channels=VALUES(push_channels)
            """), {
                "t": tenant_id, "u": user_id, "r": payload.get("role"),
                "c": json.dumps(payload.get("cards", []), ensure_ascii=False),
                "k": json.dumps(payload.get("kpi_metrics", []), ensure_ascii=False),
                "sf": payload.get("silence_from"), "st": payload.get("silence_to"),
                "th": json.dumps(payload.get("thresholds", {}), ensure_ascii=False),
                "pc": json.dumps(payload.get("push_channels", {}), ensure_ascii=False),
            })
    except Exception as e:
        log.warning("upsert_layout failed: %s", e)


def all_users() -> list[tuple[int, int]]:
    """枚举所有需要生成早报的 (tenant, user) 对. 简化: 从 briefing_layout, 否则空."""
    try:
        with db().begin() as conn:
            rows = conn.execute(text(
                "SELECT DISTINCT tenant_id, user_id FROM briefing_layout"
            )).all()
        return [(int(r[0]), int(r[1])) for r in rows]
    except Exception:
        return []
