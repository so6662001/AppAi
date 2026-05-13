"""FastAPI 入口 - 暴露 /v1/dsl/compile + /v1/dsl/execute + 健康检查。"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .models import DSL, CompileContext, CompileError
from .compiler import DSLCompiler
from .registry import load_registry


METRICS_DIR = Path(os.environ.get(
    "METRICS_DIR",
    Path(__file__).resolve().parents[3] / "metrics"
))

app = FastAPI(title="DSL Compiler", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# 启动时加载
registry = load_registry(METRICS_DIR)
compiler = DSLCompiler(registry)


# -------------------- IO --------------------

class CompileRequest(BaseModel):
    dsl: DSL
    context: CompileContext


class CompileResponse(BaseModel):
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)
    tables_used: list[str]
    metrics_expanded: list[str]
    est_rows: int | None
    warnings: list[str]
    biz_token_estimate: int


# -------------------- Endpoints --------------------

@app.get("/health")
def health():
    return {"status": "ok", "metrics_loaded": len(registry)}


@app.get("/v1/metrics")
def list_metrics(domain: str | None = None, business_line: str | None = None):
    items = registry.all_metrics()
    if domain:
        items = [m for m in items if (m.domain or "").upper() == domain.upper()]
    if business_line:
        items = [m for m in items if business_line in (m.applicable or [])]
    return {
        "total": len(items),
        "items": [
            {
                "code": m.code, "name": m.name, "label": m.label,
                "domain": m.domain, "fact": m.fact, "semantics": m.semantics,
                "sensitivity": m.sensitivity, "applicable": m.applicable,
                "version": m.version, "status": m.status,
            } for m in items
        ]
    }


@app.get("/v1/metrics/{key}")
def get_metric(key: str):
    m = registry.get(key)
    if not m:
        raise HTTPException(404, f"metric not found: {key}")
    return m.model_dump()


@app.post("/v1/dsl/compile", response_model=CompileResponse)
def compile_dsl(req: CompileRequest):
    try:
        result = compiler.compile(req.dsl, req.context)
        return CompileResponse(**result.model_dump())
    except CompileError as e:
        raise HTTPException(400, detail={"code": e.code, "message": e.message, "hint": e.hint})


@app.post("/v1/dsl/preview")
def preview_only(req: CompileRequest):
    """只生成 SQL, 不计费, 给注册中心 SQL 预览面板用。"""
    try:
        result = compiler.compile(req.dsl, req.context)
        return {"sql": result.sql, "params": result.params,
                "tables_used": result.tables_used, "warnings": result.warnings}
    except CompileError as e:
        raise HTTPException(400, detail={"code": e.code, "message": e.message, "hint": e.hint})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
