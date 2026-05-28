"""Pydantic / dataclass 模型 - 画像引擎用."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, Field


class KpiDef(BaseModel):
    code: str
    weight: float = 0.1
    direction: str = "HIGHER"                    # HIGHER/LOWER/NEUTRAL
    label: str = ""
    benchmark: bool = False
    peer_compare: bool = False


class ActionItem(BaseModel):
    label: str
    type: str = "navigate"                       # navigate/chat/action
    path: Optional[str] = None
    prompt: Optional[str] = None
    handler: Optional[str] = None


class RuleDef(BaseModel):
    id: str
    category: str = "WEAKNESS"                   # WEAKNESS/RISK/OPPORTUNITY/COMPLIANCE
    severity: str = "MEDIUM"                     # LOW/MEDIUM/HIGH
    title: str
    when: str                                    # 条件表达式
    finding: str = ""                            # 触发后输出
    impact: str = ""
    actions: list[ActionItem] = Field(default_factory=list)
    score_impact: int = 5


class RoleProfileDef(BaseModel):
    role_code: str
    role_name: str
    business_line: str = "ALL"
    level: str = "STAFF"
    focus_areas: list[str] = Field(default_factory=list)
    primary_kpis: list[KpiDef] = Field(default_factory=list)
    rules: list[RuleDef] = Field(default_factory=list)
    routines: list[str] = Field(default_factory=list)
    education: list[dict] = Field(default_factory=list)


# ----- 输入: 一次诊断的上下文 -----
@dataclass
class InsightContext:
    tenant_id: int
    user_id: int
    role_code: str
    period_month: str
    profile: RoleProfileDef                       # 该岗位的配置 (来自 YAML)
    kpi_values: dict[str, float]                  # 当前 KPI 真实值 (来自 query-engine)
    benchmarks: dict[str, dict]                   # {code: {p25,p50,p75,top10,direction}}
    peer_avgs: dict[str, float]                   # 同组员均值 (按 role + 同业务线)
    extras: dict = field(default_factory=dict)    # 其他动态变量 (e.g. potential, gap_pct)


# ----- 输出: 单条诊断 -----
class Finding(BaseModel):
    rule_id: str
    title: str
    category: str
    severity: str
    finding_text: str
    impact_text: str
    score_impact: int
    actions: list[ActionItem]
    context_values: dict = Field(default_factory=dict)


# ----- 输出: 完整画像快照 -----
class InsightSnapshot(BaseModel):
    tenant_id: int
    user_id: int
    role_code: str
    role_name: str
    snap_date: str
    period_month: str
    # 总分
    health_score: int
    health_level: str                              # A/B/C/D/E
    trend_vs_last: int = 0
    # 评分明细
    score_breakdown: dict[str, dict]               # {focus_area: {score, contrib, kpis}}
    kpi_radar: list[dict]                          # 用于雷达图 [{code, label, value, p50, mine_score}]
    # 短板/风险/机会
    findings: list[Finding]
    finding_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    # AI 行动 Top 3
    top_actions: list[dict] = Field(default_factory=list)
    explain_trace: list[str] = Field(default_factory=list)


# ----- 钻取相关 -----
class DrilldownPath(BaseModel):
    metric_code: str
    paths: list[dict]                              # [{order, dim_code, dim_label, viz, topn, ai_prompt}]


class DrilldownAttribution(BaseModel):
    """钻取 AI 归因结果."""
    metric_code: str
    metric_label: str
    period: str
    current: float
    previous: Optional[float] = None
    delta_abs: Optional[float] = None
    delta_pct: Optional[float] = None
    # Top 贡献维度
    top_contributors: list[dict] = Field(default_factory=list)
    summary_text: str = ""
    suggested_actions: list[ActionItem] = Field(default_factory=list)
