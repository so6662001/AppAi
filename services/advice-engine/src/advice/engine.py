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
        # 已对输入做字符白名单严格过滤 (allowed set), 字面量都已替换;
        # 此处 eval 仅做算术/比较, 无任意代码执行风险
        return bool(eval(expr_eval, {"__builtins__": {}}, {}))  # nosec B307
    except Exception:
        return False


DSL_COMPILER_URL = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")
QUERY_ENGINE_URL = os.environ.get("QUERY_ENGINE_URL", "http://localhost:8800")


def _fetch_metric_value(tenant_id: int, metric_name: str,
                        preset: str = "yesterday") -> float | None:
    """编译并执行单指标查询, 返回值. 失败返回 None."""
    try:
        import httpx
        r = httpx.post(f"{DSL_COMPILER_URL}/v1/dsl/compile", json={
            "dsl": {"metrics": [metric_name], "time": {"preset": preset, "grain": "day"}, "limit": 1},
            "context": {"tenant_id": tenant_id, "user_id": 0, "business_line": "TRADE",
                         "allowed_metrics": ["__ALL__"]},
        }, timeout=8)
        if r.status_code != 200: return None
        c = r.json()
        r2 = httpx.post(f"{QUERY_ENGINE_URL}/v1/query/execute", json={
            "sql": c["sql"], "params": c.get("params", {}), "row_limit": 1,
        }, headers={"X-Tenant-Id": str(tenant_id), "X-User-Id": "0"},
        timeout=15)
        if r2.status_code != 200: return None
        rows = r2.json().get("rows", [])
        if not rows: return None
        v = rows[0].get(metric_name)
        return float(v) if v is not None else None
    except Exception as e:
        log.debug("fetch %s fail: %s", metric_name, e)
        return None


# 上下文默认值 - 当指标拉取失败时用 (避免规则永久失效)
_CTX_DEFAULTS = {
    "forecast_index_price_nextweek": 0,
    "listed_price": 0,
    "daily_inv_tonnage": 0,
    "avg_inv_tonnage": 0,
    "stockout_risk_score": 0,
    "overstock_risk_score": 0,
    "unhedged_tonnage": 0,
    "hedge_position_limit": 1_000_000,
    "aging_181_365_amount": 0,
    "inv_amount": 1,           # 防止 /0
}


def _ctx_for_rule(rule: ActionRule, tenant_id: int) -> dict:
    """实时拉规则用到的指标. 静态键 = _CTX_DEFAULTS, 真查覆盖."""
    ctx = dict(_CTX_DEFAULTS)
    needed = [k for k in _CTX_DEFAULTS if k in (rule.when or "")]
    for metric in needed:
        v = _fetch_metric_value(tenant_id, metric)
        if v is not None:
            ctx[metric] = v
    return ctx


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
        for r in rules:
            try:
                ctx = _ctx_for_rule(r, tid)
            except Exception:
                log.exception("ctx build failed for rule %s", r.id); continue
            if evaluate_when(r.when, ctx):
                try:
                    write_inbox(tid, r, ctx)
                    hits += 1
                    log.info("ADVICE %s tenant=%s", r.id, tid)
                except Exception:
                    log.exception("write_inbox failed")
    return hits
