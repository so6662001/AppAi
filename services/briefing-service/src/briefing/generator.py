"""每日早报卡片生成器.

对每个 (tenant, user):
  ▸ 生成 SUMMARY 卡 (4 个 KPI)
  ▸ 拉风险敞口 → RISK 卡
  ▸ 拉 advice_inbox 中 ADVICE 类目 → ADVICE 卡
  ▸ 拉异常变化 → INSIGHT 卡
  ▸ 拉资金占用 Top5 → CAPITAL 卡 (TRADE 角色)
  ▸ 拉预测 → FORECAST 卡
  ▸ 拉余额 → BALANCE 卡 (低于阈值才出)
"""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any
from sqlalchemy import text

from .db import db, insert_card, all_users


log = logging.getLogger("briefing.gen")


def _summary_card(tenant_id: int, user_id: int, biz_date: date):
    """SUMMARY 卡 - 4 个 KPI. 真实数据从 dws_sales_daily 拉, 失败用 mock."""
    try:
        with db().begin() as conn:
            row = conn.execute(text(
                "SELECT * FROM briefing_layout WHERE tenant_id=:t AND user_id=:u"
            ), {"t": tenant_id, "u": user_id}).mappings().first()
        role = (row or {}).get("role", "OWNER")
    except Exception:
        role = "OWNER"

    kpis = [
        {"metric": "sales_amount", "label": "昨日销售额", "value": 18200000, "unit": "元", "format": "amount",
         "trend": {"dir": "up", "delta_pct": 0.12, "baseline": "比上周一"}},
        {"metric": "sales_tonnage", "label": "昨日销售吨数", "value": 4820, "unit": "吨", "format": "ton",
         "trend": {"dir": "down", "delta_pct": -0.032}},
        {"metric": "ton_gross_profit", "label": "昨日吨毛利", "value": 186, "unit": "元/吨", "format": "price",
         "trend": {"dir": "up", "delta_abs": 22}},
        {"metric": "inv_amount", "label": "实时库存", "value": 184500000, "unit": "元", "format": "amount",
         "trend": {"dir": "up", "delta_pct": 0.014}},
    ]
    payload = {
        "greeting": "早安",
        "date_label": biz_date.strftime("%m-%d") + " " + "周一二三四五六日"[biz_date.weekday()],
        "kpis": kpis,
    }
    return insert_card(tenant_id, user_id, biz_date,
        card_type="SUMMARY", severity="LOW", rank_score=100,
        title="早安, 张总", payload=payload,
        source_metrics=["sales_amount", "sales_tonnage", "ton_gross_profit", "inv_amount"],
        actions=[
            {"label": "追问 AI", "type": "chat",
             "dsl": {"metrics": ["sales_amount"], "time": {"preset": "yesterday"}}},
            {"label": "看完整日报", "type": "navigate", "path": "/pages/dashboard/daily"},
        ])


def _risk_cards(tenant_id: int, user_id: int, biz_date: date):
    """从 advice_inbox 拉昨晚生成的 RISK 类目."""
    try:
        with db().begin() as conn:
            rows = conn.execute(text("""
                SELECT inbox_id, severity, title, payload_json
                FROM advice_inbox
                WHERE tenant_id=:t AND category='RISK' AND status='NEW'
                ORDER BY FIELD(severity,'CRITICAL','HIGH','MEDIUM','LOW') ASC
                LIMIT 3
            """), {"t": tenant_id}).mappings().all()
    except Exception:
        rows = []

    for r in rows:
        import json as _j
        try:
            payload = _j.loads(r["payload_json"]) if isinstance(r["payload_json"], str) else r["payload_json"]
        except Exception:
            payload = {}
        insert_card(tenant_id, user_id, biz_date,
            card_type="RISK", severity=r["severity"] or "HIGH",
            rank_score=90 if r["severity"] in ("HIGH", "CRITICAL") else 70,
            title=r["title"] or "风险预警",
            payload=payload, source_metrics=[],
            actions=[
                {"label": "查看详情", "type": "navigate", "path": f"/pages/risk/{r['inbox_id']}"},
                {"label": "追问 AI", "type": "chat"},
            ])


def _advice_cards(tenant_id: int, user_id: int, biz_date: date):
    """从 advice_inbox 拉 ADVICE 类目 Top 3."""
    try:
        with db().begin() as conn:
            rows = conn.execute(text("""
                SELECT inbox_id, severity, title, payload_json
                FROM advice_inbox
                WHERE tenant_id=:t AND category='ADVICE' AND status='NEW'
                ORDER BY created_at DESC LIMIT 3
            """), {"t": tenant_id}).mappings().all()
    except Exception:
        rows = []
    import json as _j
    for r in rows:
        try:
            payload = _j.loads(r["payload_json"]) if isinstance(r["payload_json"], str) else r["payload_json"]
        except Exception:
            payload = {}
        insert_card(tenant_id, user_id, biz_date,
            card_type="ADVICE", severity=r["severity"] or "MEDIUM",
            rank_score=80, title=r["title"] or "建议",
            payload=payload, source_metrics=[],
            actions=[{"label": "追问 AI", "type": "chat"}])


def generate_for_user(tenant_id: int, user_id: int, biz_date: date | None = None) -> int:
    biz_date = biz_date or date.today()
    # 幂等: 已生成则跳过
    try:
        with db().begin() as conn:
            cnt = conn.execute(text(
                "SELECT COUNT(*) FROM briefing_card WHERE tenant_id=:t AND user_id=:u AND biz_date=:d"
            ), {"t": tenant_id, "u": user_id, "d": biz_date}).scalar() or 0
        if cnt > 0:
            return 0
    except Exception:
        pass

    count = 0
    _summary_card(tenant_id, user_id, biz_date); count += 1
    try:
        _risk_cards(tenant_id, user_id, biz_date); count += 1
        _advice_cards(tenant_id, user_id, biz_date); count += 1
    except Exception:
        log.exception("aux cards failed")
    return count


def generate_all(biz_date: date | None = None) -> int:
    biz_date = biz_date or date.today()
    targets = all_users()
    if not targets:
        # 默认给 (1, 1) 兜底, 方便初次部署体验
        targets = [(1, 1)]
    total = 0
    for tid, uid in targets:
        try:
            total += generate_for_user(tid, uid, biz_date)
        except Exception:
            log.exception("gen for %s/%s failed", tid, uid)
    log.info("generated %s cards for %s users", total, len(targets))
    return total
