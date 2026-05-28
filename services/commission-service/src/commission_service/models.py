"""提成方案 / 规则 / 计算结果数据结构 (Pydantic + dataclass)."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ---------- 配置层 ----------

class CommissionScheme(BaseModel):
    """提成方案 - 与 commission_scheme 表对应."""
    tenant_id: int
    scheme_id: int
    scheme_code: str
    scheme_name: str
    business_line: str = Field(default="TRADE")
    base_type: str = Field(default="LISTED_GROSS_PROFIT",
                           description="LISTED_GROSS_PROFIT/TON_GROSS_PROFIT/NET_PROFIT/PROCESSING_FEE/REVENUE/SPREAD")
    rate_default: float = 0.30
    ar_interest_rate: float = 0.000125
    inv_interest_rate: float = 0.000150
    prepay_interest_rate: float = 0.000125
    use_ar_interest: bool = True
    use_inv_interest: bool = True
    use_prepay_interest: bool = True
    use_customer_seg: bool = True
    use_direct_indirect: bool = True
    use_biz_fee_deduct: bool = True
    use_roundoff_deduct: bool = True
    min_commission_per_month: Optional[float] = None
    max_commission_per_month: Optional[float] = None
    quarter_bonus_pct: float = 0.0
    yearly_adjust_pct: float = 0.0
    effective_from: date
    effective_to: Optional[date] = None
    status: str = "ACTIVE"


class CommissionRuleLine(BaseModel):
    """提成规则明细 - commission_rule_line 表."""
    tenant_id: int
    scheme_id: int
    rule_id: int
    rule_label: str = ""
    priority: int = 100
    match_sales_mode: Optional[str] = None
    match_settle_type: Optional[str] = None
    match_customer_seg: Optional[str] = None
    match_product_type: Optional[str] = None
    match_origin_id: Optional[int] = None
    match_grade_family: Optional[str] = None
    match_org_id: Optional[int] = None
    match_min_margin: Optional[float] = None
    match_max_margin: Optional[float] = None
    rate: float
    rate_unit: str = "PCT"
    is_active: bool = True


# ---------- 输入业绩 ----------

@dataclass
class SalesOrderInput:
    """一条用于计提的销售订单输入数据."""
    order_no: str
    order_date: date
    rep_id: int
    customer_id: int
    customer_seg: str = "VOLUME"     # PROFIT/VOLUME/A/B/C
    sales_mode: str = "DIRECT"       # DIRECT/INDIRECT/TRANSIT/SHELL
    settle_type: str = "T+30"        # CASH/T+7/T+30/T+60/T+90/BANK_ACCEPT/COMMERCIAL_ACCEPT
    product_type: str = "板材"
    origin_id: Optional[int] = None
    grade_family: Optional[str] = None
    org_id: Optional[int] = None
    tonnage: float = 0.0
    revenue: float = 0.0             # 不含税收入
    cost: float = 0.0
    listed_gross_profit: float = 0.0  # 挂牌毛利
    ton_gross_profit: float = 0.0     # 吨毛利元
    processing_fee: float = 0.0
    spread_per_ton: float = 0.0       # 撮合差价 (皮包公司用)
    # 资金占用 (按月汇总传入, 也可按单)
    avg_ar_days: float = 30.0
    avg_ar_balance: float = 0.0
    avg_inv_days: float = 0.0
    avg_inv_balance: float = 0.0
    avg_prepay_days: float = 0.0
    avg_prepay_balance: float = 0.0
    # 暗规则金额
    biz_fee_amt: float = 0.0
    roundoff_amt: float = 0.0
    is_local_sales: bool = True


@dataclass
class CalcContext:
    """一次计算的上下文 (一个销售员 一个月)."""
    tenant_id: int
    period_month: str       # 2026-05
    rep_id: int
    rep_name: str = ""
    scheme: Optional[CommissionScheme] = None
    rules: list[CommissionRuleLine] = field(default_factory=list)
    orders: list[SalesOrderInput] = field(default_factory=list)


# ---------- 输出结果 ----------

class CommissionLineDetail(BaseModel):
    """每条订单/或每条规则的子计算明细."""
    order_no: str
    matched_rule_id: Optional[int]
    matched_rule_label: str
    base_amount: float
    rate: float
    rate_unit: str
    raw_commission: float
    adjust_direct: float = 1.0
    adjust_customer_seg: float = 1.0


class CommissionResult(BaseModel):
    tenant_id: int
    period_month: str
    rep_id: int
    rep_name: str = ""
    scheme_id: int
    scheme_code: str = ""
    # 基数
    gross_profit_listed: float = 0
    gross_profit_ton: float = 0
    revenue_amount: float = 0
    tonnage: float = 0
    processing_fee: float = 0
    spread_amount: float = 0
    # 扣减
    ar_interest_amt: float = 0
    inv_interest_amt: float = 0
    prepay_interest_amt: float = 0
    biz_fee_amt: float = 0
    roundoff_amt: float = 0
    # 调整
    direct_indirect_adj: float = 1.0
    customer_seg_adj: float = 1.0
    # 结果
    base_amount: float = 0
    rate_effective: float = 0
    commission_calc: float = 0
    commission_floor: Optional[float] = None
    commission_cap: Optional[float] = None
    commission_final: float = 0
    line_details: list[CommissionLineDetail] = Field(default_factory=list)
    explain_trace: list[str] = Field(default_factory=list)
