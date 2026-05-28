"""FastAPI 入口: 提成方案/规则 CRUD + 计算端点."""
from __future__ import annotations
import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from .models import (
    CalcContext, CommissionScheme, CommissionRuleLine,
    SalesOrderInput, CommissionResult,
)
from .engine import calculate
from .templates import get_template

try:
    import sys
    sys.path.append(os.environ.get("SHARED_PATH", "/opt/shared"))
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../_shared")))
    import observability  # type: ignore
except Exception:
    observability = None

log = logging.getLogger("commission")
app = FastAPI(title="commission-service", version="0.1.0")
if observability:
    observability.setup(app, service_name="commission-service")


class CalcRequest(BaseModel):
    tenant_id: int
    period_month: str
    rep_id: int
    rep_name: str = ""
    scheme: CommissionScheme
    rules: list[CommissionRuleLine] = []
    orders: list[SalesOrderInput]


class CalcResponse(BaseModel):
    result: CommissionResult


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/v1/templates")
def list_templates():
    """返回 4 套内置模板 (供租户开户时选择)."""
    return {
        bl: {
            "scheme_code": fn(0)[0].scheme_code,
            "scheme_name": fn(0)[0].scheme_name,
            "base_type": fn(0)[0].base_type,
            "rate_default": fn(0)[0].rate_default,
            "rule_count": len(fn(0)[1]),
        }
        for bl, fn in __import__("commission_service.templates", fromlist=["TEMPLATES"]).TEMPLATES.items()
    }


@app.get("/v1/templates/{business_line}")
def get_one_template(business_line: str):
    """拉取某业务线模板 (含规则明细)."""
    try:
        scheme, rules = get_template(business_line, tenant_id=0)
        return {"scheme": scheme.model_dump(mode="json"),
                "rules": [r.model_dump(mode="json") for r in rules]}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/v1/calc", response_model=CalcResponse)
def calc(req: CalcRequest) -> CalcResponse:
    """无副作用计算: 给定方案/规则/订单, 输出 CommissionResult."""
    ctx = CalcContext(
        tenant_id=req.tenant_id,
        period_month=req.period_month,
        rep_id=req.rep_id,
        rep_name=req.rep_name,
        scheme=req.scheme,
        rules=list(req.rules),
        orders=list(req.orders),
    )
    res = calculate(ctx)
    return CalcResponse(result=res)


@app.post("/v1/calc/by-template")
def calc_by_template(business_line: str, tenant_id: int, period_month: str,
                     rep_id: int, rep_name: str, orders: list[SalesOrderInput]):
    """直接套用内置模板做计算 (用于演示/快速试算)."""
    try:
        scheme, rules = get_template(business_line, tenant_id=tenant_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    ctx = CalcContext(tenant_id=tenant_id, period_month=period_month,
                      rep_id=rep_id, rep_name=rep_name,
                      scheme=scheme, rules=rules, orders=list(orders))
    return {"result": calculate(ctx).model_dump(mode="json")}
