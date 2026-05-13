"""加载 metrics_forecast.yaml 中的 action_rules, 周期扫描生成 advice_inbox 记录."""
from __future__ import annotations
import os
import json
import logging
from datetime import date, datetime
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

import yaml
from sqlalchemy import create_engine, text


log = logging.getLogger("advice.engine")

METRICS_DIR = Path(os.environ.get("METRICS_DIR", "/workspace/metrics"))
DB_URL = os.environ.get("DB_URL",
    "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4")

_engine = None
def db():
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL, pool_pre_ping=True, future=True)
    return _engine


@dataclass
class ActionRule:
    id: str
    title: str
    severity: str
    when: str
    advice: str
    suggested_actions: list[dict] = field(default_factory=list)


def load_rules() -> list[ActionRule]:
    out: list[ActionRule] = []
    for f in sorted(METRICS_DIR.glob("metrics_*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for r in (data.get("action_rules") or []):
            out.append(ActionRule(
                id=r["id"],
                title=r.get("title", r["id"]),
                severity=r.get("severity", "MEDIUM"),
                when=r.get("when", ""),
                advice=r.get("advice", ""),
                suggested_actions=r.get("suggested_actions") or [],
            ))
    return out


def evaluate_when(expr: str, ctx: dict) -> bool:
    """安全的 when 求值. 支持的运算: > < >= <= == != AND OR ()."""
    if not expr:
        return False
    # 替换变量为字面量
    expr_eval = expr
    for k, v in sorted(ctx.items(), key=lambda x: -len(x[0])):
        if isinstance(v, (int, float)):
            expr_eval = expr_eval.replace(k, str(v))
    expr_eval = expr_eval.replace(" AND ", " and ").replace(" OR ", " or ")
    # 只允许安全字符
    allowed = set("0123456789.+-*/()<>!= andornot ")
    if not all(c in allowed or c.isspace() for c in expr_eval):
        # 含未替换的变量 → 视为不成立
        return False
    try:
        return bool(eval(expr_eval, {"__builtins__": {}}, {}))
    except Exception:
        return False


def _ctx_for_rule(rule: ActionRule, tenant_id: int) -> dict:
    """加载该规则需要的指标值. 演示用 mock; 真实接 query-engine."""
    # 几个常见上下文键 - 这里假设由别的指标计算服务塞到 Redis 或表
    return {
        "forecast_index_price_nextweek": 4150,
        "listed_price": 4180,
        "daily_inv_tonnage": 1820,
        "avg_inv_tonnage": 1480,
        "stockout_risk_score": 0.3,
        "overstock_risk_score": 0.5,
        "unhedged_tonnage": 800,
        "hedge_position_limit": 1000,
        "aging_181_365_amount": 5_000_000,
        "inv_amount": 50_000_000,
    }


def write_inbox(tenant_id: int, rule: ActionRule, ctx: dict):
    title = rule.title
    try:
        advice_text = rule.advice.format(**ctx)
    except Exception:
        advice_text = rule.advice
    payload = {"reason": advice_text, "suggested_actions": rule.suggested_actions, "ctx": ctx}
    with db().begin() as conn:
        conn.execute(text("""
            INSERT INTO advice_inbox
              (tenant_id, user_id, role, category, rule_id, severity, title, payload_json, status)
            VALUES (:tid, NULL, '', 'ADVICE', :rid, :sv, :ti, :pl, 'NEW')
        """), {"tid": tenant_id, "rid": rule.id, "sv": rule.severity,
               "ti": title, "pl": json.dumps(payload, ensure_ascii=False, default=str)})


def _all_tenants() -> list[int]:
    try:
        with db().begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT tenant_id FROM tenant_wallet")).all()
        return [int(r[0]) for r in rows] or [1]
    except Exception:
        return [1]


def scan_once() -> int:
    rules = load_rules()
    hits = 0
    for tid in _all_tenants():
        ctx_base = _ctx_for_rule(None, tid) if False else None
        for r in rules:
            ctx = _ctx_for_rule(r, tid)
            if evaluate_when(r.when, ctx):
                try:
                    write_inbox(tid, r, ctx)
                    hits += 1
                    log.info("ADVICE %s tenant=%s", r.id, tid)
                except Exception:
                    log.exception("write_inbox failed")
    return hits
