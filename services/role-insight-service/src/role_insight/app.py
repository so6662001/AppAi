"""FastAPI 入口."""
from __future__ import annotations
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from . import loader, engine, drilldown
from .models import (
    InsightContext, InsightSnapshot, RoleProfileDef,
    DrilldownPath, DrilldownAttribution,
)

log = logging.getLogger("role-insight")
app = FastAPI(title="role-insight-service", version="0.1.0")

try:
    import sys
    sys.path.append(os.environ.get("SHARED_PATH", "/opt/shared"))
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../_shared")))
    import observability  # type: ignore
    observability.setup(app, service_name="role-insight-service")
except Exception:
    pass


@app.on_event("startup")
def _warmup():
    n = len(loader.load_all())
    log.info("loaded %d role profiles", n)


@app.get("/healthz")
def healthz():
    return {"ok": True, "loaded": len(loader._cache)}


@app.get("/v1/roles")
def list_roles():
    """列出所有可用岗位."""
    return [
        {
            "role_code": p.role_code, "role_name": p.role_name,
            "business_line": p.business_line, "level": p.level,
            "focus_areas": p.focus_areas, "kpi_count": len(p.primary_kpis),
            "rule_count": len(p.rules),
        }
        for p in loader.load_all().values()
    ]


@app.get("/v1/roles/{role_code}")
def get_role(role_code: str):
    p = loader.get_profile(role_code)
    if not p:
        raise HTTPException(404, f"role {role_code} not found")
    return p.model_dump(mode="json")


# ----- 诊断接口 -----
class DiagnoseRequest(BaseModel):
    tenant_id: int
    user_id: int
    role_code: str
    period_month: str
    kpi_values: dict[str, float]
    benchmarks: dict[str, dict] = {}     # {code: {p25,p50,p75,top10,direction}}
    peer_avgs: dict[str, float] = {}
    extras: dict = {}


@app.post("/v1/diagnose", response_model=InsightSnapshot)
def diagnose(req: DiagnoseRequest):
    """根据传入的 KPI 值跑画像诊断."""
    profile = loader.get_profile(req.role_code)
    if not profile:
        raise HTTPException(404, f"role {req.role_code} not found")
    ctx = InsightContext(
        tenant_id=req.tenant_id, user_id=req.user_id,
        role_code=req.role_code, period_month=req.period_month,
        profile=profile,
        kpi_values=req.kpi_values,
        benchmarks=req.benchmarks,
        peer_avgs=req.peer_avgs,
        extras=req.extras,
    )
    snap = engine.diagnose(ctx)
    return snap


# ----- 钻取推荐 -----
@app.get("/v1/drilldown/{metric_code}/paths", response_model=DrilldownPath)
def drill_paths(metric_code: str):
    return drilldown.recommend_paths(metric_code)


# ----- 钻取归因 -----
class AttrRequest(BaseModel):
    metric_code: str
    metric_label: str
    current: float
    previous: Optional[float] = None
    breakdown: list[dict]
    period: str = "本期 vs 上期"


@app.post("/v1/drilldown/attribute", response_model=DrilldownAttribution)
def attribute(req: AttrRequest):
    return drilldown.attribute_change(
        metric_code=req.metric_code,
        metric_label=req.metric_label,
        current=req.current,
        previous=req.previous,
        breakdown=req.breakdown,
        period=req.period,
    )


# ----- 演示快照 (前端 demo 用, 不需要后端真数据) -----
@app.get("/v1/demo/snapshot/{role_code}")
def demo_snapshot(role_code: str):
    """演示用: 给前端返回一个完整的画像样例.
    实际生产环境由 [v1/diagnose] 真实计算."""
    profile = loader.get_profile(role_code)
    if not profile:
        raise HTTPException(404, f"role {role_code} not found")
    if role_code == "TRADE_SALES_REP":
        ctx = _demo_ctx_sales_rep(profile)
    elif role_code == "TRADE_OWNER":
        ctx = _demo_ctx_owner(profile)
    elif role_code == "FINANCE_CTRL":
        ctx = _demo_ctx_finance(profile)
    else:
        raise HTTPException(404, f"no demo for {role_code}")
    snap = engine.diagnose(ctx)
    return snap


def _demo_ctx_sales_rep(profile: RoleProfileDef) -> InsightContext:
    return InsightContext(
        tenant_id=1, user_id=200237, role_code="TRADE_SALES_REP",
        period_month="2026-05",
        profile=profile,
        kpi_values={
            "my_ton_gross_profit": 156.0,
            "my_active_customers": 8,
            "my_ar_balance": 1_800_000,
            "my_aged_ar": 280_000,
            "my_aged_ar_pct": 0.18,
            "my_commission_calc": 18720,
            "my_new_customer_count": 2,
            "my_new_customer_count_qtr": 0,
            "team_avg_ton_gross_profit": 186.0,
            "top2_customer_share": 0.74,
            "indirect_share": 0.45,
            "my_tonnage_mom_pct": -0.25,
            "my_biz_fee_amt": 3500,
        },
        benchmarks={
            "my_ton_gross_profit": {"p25":120, "p50":165, "p75":215, "top10":280, "direction":"HIGHER"},
        },
        peer_avgs={
            "my_new_customer_count_qtr": 2.4,
        },
        extras={
            "gap_pct": 0.16, "potential": 13800, "commission_loss": 4200,
            "top1_name": "客户A", "top1_pct": 0.42,
            "risk_amount": 84000, "peer_avg": 2.4,
            "forecast_commission": 14200, "team_avg": 186,
            "my_tonnage": 350,
        },
    )


def _demo_ctx_owner(profile: RoleProfileDef) -> InsightContext:
    return InsightContext(
        tenant_id=1, user_id=1, role_code="TRADE_OWNER",
        period_month="2026-05",
        profile=profile,
        kpi_values={
            "sales_amount": 18_200_000,
            "ton_gross_profit": 186,
            "net_margin_pct": 0.036,
            "capital_occupation": 56_800_000,
            "customer_risk_score": 32,
            "combined_hedge_pnl": 50_000,
            "ccc_days": 48,
            "top10_customer_capital_share": 0.71,
            "locked_unhedged_tonnage": 580,
            "biz_fee_mom_pct": 0.42,
            "roundoff_mom_pct": 0.15,
            "top1_supplier_share": 0.48,
        },
        benchmarks={
            "net_margin_pct": {"p25":0.018,"p50":0.032,"p75":0.052,"top10":0.082, "direction":"HIGHER"},
            "ccc_days":       {"p25":70,   "p50":56,    "p75":38,   "top10":22, "direction":"LOWER"},
        },
        peer_avgs={},
        extras={
            "p50": 0.032, "gap": 0.004, "potential": 8_600_000,
            "top10_share": 0.71, "top10_amount": 40_300_000, "top1_amount": 8_400_000,
            "ratio": 0.18, "risk_amount": 58_000, "max_swing": 180, "worst": 104_000,
            "capital_per_day": 280_000, "interest": 4_600_000,
            "biz_fee_amt": 8_420, "top1_supplier_name": "沙钢", "affected_tonnage": 2300,
        },
    )


def _demo_ctx_finance(profile: RoleProfileDef) -> InsightContext:
    return InsightContext(
        tenant_id=1, user_id=2, role_code="FINANCE_CTRL",
        period_month="2026-05",
        profile=profile,
        kpi_values={
            "current_ratio": 1.85,
            "debt_to_asset": 0.582,
            "ccc_days": 48,
            "ar_aging_181_365_pct": 0.062,
            "ar_aging_181_365_amount": 1_420_000,
            "biz_fee_to_gp_ratio": 0.12,
            "biz_fee_amt": 8_420,
            "intercompany_eliminate_match_pct": 0.92,
            "cf_operating": 14_200_000,
            "cf_operating_lastmonth": 12_800_000,
            "actual_tax_rate": 0.262,
            "legal_tax_rate": 0.25,
        },
        benchmarks={
            "debt_to_asset": {"p25":0.78,"p50":0.65,"p75":0.52,"top10":0.42, "direction":"LOWER"},
            "ccc_days":      {"p25":70, "p50":56,   "p75":38,   "top10":22, "direction":"LOWER"},
            "current_ratio": {"p25":1.1,"p50":1.5,  "p75":2.0,  "top10":2.8, "direction":"HIGHER"},
        },
        peer_avgs={},
        extras={
            "p50": 56, "gap": -8, "extra_capital": 5_600_000, "interest": 252_000,
            "ratio": 0.024, "amt": 1_420_000, "provision": 426_000,
            "gap_count": 12, "potential_amt": 380_000,
            "extra_tax": 184_000,
        },
    )
