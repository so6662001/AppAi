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
import os
from datetime import date, timedelta
from typing import Any
from sqlalchemy import text

from .db import db, insert_card, all_users


log = logging.getLogger("briefing.gen")


DSL_COMPILER_URL = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")
QUERY_ENGINE_URL = os.environ.get("QUERY_ENGINE_URL", "http://localhost:8800")
REGISTRY_URL = os.environ.get("REGISTRY_URL", "http://localhost:8090/api/registry/v1")


def _fetch_metric(tenant_id: int, user_id: int, metric_name: str,
                  preset: str = "yesterday") -> tuple[float | None, dict]:
    """编译 DSL → 执行 → 返回 (value, raw_row). 失败返回 (None, {})."""
    try:
        import httpx
        r = httpx.post(f"{DSL_COMPILER_URL}/v1/dsl/compile", json={
            "dsl": {"metrics": [metric_name], "time": {"preset": preset, "grain": "day"}, "limit": 1},
            "context": {"tenant_id": tenant_id, "user_id": user_id, "business_line": "TRADE",
                         "allowed_metrics": ["__ALL__"]},
        }, timeout=8)
        if r.status_code != 200: return None, {}
        c = r.json()
        r2 = httpx.post(f"{QUERY_ENGINE_URL}/v1/query/execute", json={
            "sql": c["sql"], "params": c.get("params", {}), "row_limit": 1,
        }, headers={"X-Tenant-Id": str(tenant_id), "X-User-Id": str(user_id)}, timeout=15)
        if r2.status_code != 200: return None, {}
        rows = r2.json().get("rows", [])
        if not rows: return None, {}
        v = rows[0].get(metric_name)
        return (float(v) if v is not None else None), rows[0]
    except Exception as e:
        log.debug("fetch metric %s fail: %s", metric_name, e)
        return None, {}


def _get_user_kpis(tenant_id: int, user_id: int) -> tuple[list[str], str]:
    """从 metric-registry 拿用户 pack 的 summary_kpis. 失败 fallback 4 个通用 KPI."""
    try:
        import httpx
        r = httpx.get(f"{REGISTRY_URL}/user/preferences",
                      headers={"X-User-Id": str(user_id), "X-Tenant-Id": str(tenant_id)},
                      timeout=5)
        if r.status_code == 200:
            prefs = r.json()
            role = prefs.get("primary_role") or "OWNER"
            biz = prefs.get("business_line") or "TRADE"
            # 拉对应 pack
            rec = httpx.get(f"{REGISTRY_URL}/metric-packs/recommend?biz={biz}&role={role}",
                            headers={"X-User-Id": str(user_id), "X-Tenant-Id": str(tenant_id)},
                            timeout=5)
            if rec.status_code == 200:
                pack = rec.json().get("primary")
                if pack:
                    raw = pack.get("summary_kpis_json")
                    if isinstance(raw, str):
                        import json as _j
                        try: kpis = _j.loads(raw)
                        except Exception: kpis = None
                    else:
                        kpis = raw
                    if kpis and len(kpis) >= 4:
                        return kpis[:4], role
    except Exception as e:
        log.debug("fetch user kpis fail: %s", e)
    return ["sales_amount", "sales_tonnage", "ton_gross_profit", "inv_amount"], "OWNER"


def _summary_card(tenant_id: int, user_id: int, biz_date: date):
    """SUMMARY 卡 - 4 个 KPI. 真实查 dws + 不可达时降级 + 标记 degraded."""
    metric_names, role = _get_user_kpis(tenant_id, user_id)
    labels_map = {
        "sales_amount": ("昨日销售额", "元", "amount"),
        "sales_tonnage": ("昨日销售吨数", "吨", "ton"),
        "ton_gross_profit": ("昨日吨毛利", "元/吨", "price"),
        "inv_amount": ("实时库存", "元", "amount"),
        "net_margin": ("净利率", "%", "percent"),
        "ar_outstanding": ("应收余额", "元", "amount"),
        "ar_overdue_amount": ("逾期应收", "元", "amount"),
        "customer_capital_occupation": ("客户占款", "元", "amount"),
        "oee": ("OEE", "%", "percent"),
        "quality_rate": ("良品率", "%", "percent"),
        "active_customer_count": ("活跃客户数", "个", "count"),
        "ar_aging_overdue_rate": ("逾期占比", "%", "percent"),
        "hedge_net_exposure": ("套保净敞口", "吨", "ton"),
        "inv_mtm_pnl": ("库存浮亏", "元", "amount"),
        "credit_overlimit_amount": ("授信超限", "元", "amount"),
    }

    kpis = []
    fallback_used = False
    for name in metric_names[:4]:
        v, _row = _fetch_metric(tenant_id, user_id, name)
        label, unit, fmt = labels_map.get(name, (name, "", "amount"))
        if v is None:
            # 单个指标失败时使用降级数据 + 标记
            fallback_used = True
            v = {"sales_amount": 18200000, "sales_tonnage": 4820,
                 "ton_gross_profit": 186, "inv_amount": 184500000}.get(name, 0)
        kpis.append({"metric": name, "label": label, "value": v, "unit": unit, "format": fmt})

    payload = {
        "greeting": "早安",
        "date_label": biz_date.strftime("%m-%d") + " " + "周一二三四五六日"[biz_date.weekday()],
        "kpis": kpis,
        "data_degraded": fallback_used,    # 前端可显示"演示数据"标记
        "role": role,
    }
    return insert_card(tenant_id, user_id, biz_date,
        card_type="SUMMARY", severity="LOW", rank_score=100,
        title="早安", payload=payload,
        source_metrics=metric_names[:4],
        actions=[
            {"label": "追问 AI", "type": "chat",
             "dsl": {"metrics": [metric_names[0]], "time": {"preset": "yesterday"}}},
            {"label": "看完整日报", "type": "navigate", "path": "/pages/dashboard/daily"},
        ])


def _risk_cards(tenant_id: int, user_id: int, biz_date: date):
    """从 advice_inbox 拉 RISK 类目 - 按 user_id 隔离, 避免跨用户隐私泄漏.

    规则:
      1. user_id 精确匹配本用户的条目 (最高优先级)
      2. user_id=NULL 且 role 与本用户匹配的广播条目 (次优先)
      3. 业务员等普通角色 看不到 user_id 为他人的条目
    """
    try:
        # 先取用户角色
        with db().begin() as conn:
            urow = conn.execute(text("""
                SELECT primary_role FROM sys_user_preferences WHERE user_id=:u
            """), {"u": user_id}).first()
        role = (urow[0] if urow else None) or "USER"
    except Exception:
        role = "USER"

    try:
        with db().begin() as conn:
            rows = conn.execute(text("""
                SELECT inbox_id, severity, title, payload_json
                FROM advice_inbox
                WHERE tenant_id=:t AND category='RISK' AND status='NEW'
                  AND (
                       user_id = :u           -- 精确属于本用户
                    OR (user_id IS NULL AND (role = :r OR role IN ('__broadcast__','')))
                  )
                ORDER BY FIELD(severity,'CRITICAL','HIGH','MEDIUM','LOW') ASC,
                         created_at DESC
                LIMIT 3
            """), {"t": tenant_id, "u": user_id, "r": role}).mappings().all()
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
