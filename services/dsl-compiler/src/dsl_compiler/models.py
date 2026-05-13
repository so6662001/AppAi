"""Pydantic 模型 - DSL 输入与 MetricDef 元数据。"""
from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# =========================================================================
# AI 输出的 DSL 结构
# =========================================================================

class DSLFilter(BaseModel):
    field: str
    op: str  # =, !=, >, >=, <, <=, in, not_in, between, like, is_null, not_null
    value: Any = None


class DSLTime(BaseModel):
    field: str = "date.date_key"
    grain: str = "day"  # day, week, month, quarter, year
    preset: Optional[str] = None
    range: Optional[dict] = None  # {"from": "2026-05-01", "to": "2026-05-13"}


class DSLCompare(BaseModel):
    mode: str  # yoy, mom, wow, dod, vs_plan, vs_budget, vs_index


class DSLOrder(BaseModel):
    field: str
    dir: str = "desc"


class DSLTopN(BaseModel):
    by: str
    n: int = 10
    others: bool = False


class DSL(BaseModel):
    metrics: list[str] = Field(..., min_length=1, max_length=6)
    dimensions: list[str] = Field(default_factory=list, max_length=5)
    filters: list[DSLFilter] = Field(default_factory=list)
    time: DSLTime
    compare: Optional[DSLCompare] = None
    order_by: list[DSLOrder] = Field(default_factory=list, alias="orderBy")
    limit: int = Field(1000, ge=1, le=50000)
    top_n: Optional[DSLTopN] = Field(default=None, alias="topN")
    format: str = "raw"

    model_config = {"populate_by_name": True}


# =========================================================================
# 执行上下文（权限 / 租户 / 业务类型）
# =========================================================================

class CompileContext(BaseModel):
    tenant_id: int
    user_id: int
    business_line: str  # TRADE / PROCESS / MILL
    scopes: list[str] = Field(default_factory=list)
    # 行级权限
    visible_org_ids: Optional[list[int]] = None
    visible_warehouse_ids: Optional[list[int]] = None
    visible_workcenter_ids: Optional[list[int]] = None
    # 计费默认参数
    bizToken_estimate_base: int = 200


# =========================================================================
# Metric 元数据 (从 metrics/*.yaml 加载)
# =========================================================================

class MetricSLA(BaseModel):
    freshness_minutes: int = 60
    availability: float = 99.5
    query_p95_ms: int = 2000


class MetricDef(BaseModel):
    name: str
    code: Optional[str] = None
    label: Optional[str] = None
    alias: Optional[str] = None
    synonyms: list[str] = Field(default_factory=list)
    domain: Optional[str] = None
    fact: Optional[str] = None
    formula: str = ""
    semantics: str = "additive"   # additive / snapshot / virtual / dimension
    time_agg: str = "sum"          # sum / avg / first / last
    format: str = "amount"
    unit: Optional[str] = None
    applicable: list[str] = Field(default_factory=lambda: ["TRADE", "PROCESS", "MILL"])
    requires_metrics: list[str] = Field(default_factory=list)
    filter_expr: Optional[str] = Field(default=None, alias="filter")
    join_tables: list[str] = Field(default_factory=list, alias="join")
    sensitivity: str = "LOW"
    bizToken_multiplier: float = 1.0
    owner: Optional[str] = None
    version: str = "1.0.0"
    status: str = "PUBLISHED"
    sla: MetricSLA = Field(default_factory=MetricSLA)
    note: Optional[str] = None
    notes: Optional[str] = None
    auth_required: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "allow"}

    @field_validator("applicable", mode="before")
    @classmethod
    def normalize_applicable(cls, v):
        if v is None:
            return ["TRADE", "PROCESS", "MILL"]
        return v


# =========================================================================
# 编译结果
# =========================================================================

class CompileResult(BaseModel):
    sql: str
    params: dict[str, Any] = Field(default_factory=dict)
    tables_used: list[str] = Field(default_factory=list)
    metrics_expanded: list[str] = Field(default_factory=list)
    est_rows: Optional[int] = None
    warnings: list[str] = Field(default_factory=list)
    biz_token_estimate: int = 0


class CompileError(Exception):
    def __init__(self, code: str, message: str, hint: Optional[str] = None):
        self.code = code
        self.message = message
        self.hint = hint
        super().__init__(f"[{code}] {message}")
