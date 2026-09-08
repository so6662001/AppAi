"""内置 4 套真实数字提成模板 (新租户开户即用)."""
from __future__ import annotations
from datetime import date
from .models import CommissionScheme, CommissionRuleLine


def trade_template(tenant_id: int = 0, scheme_id: int = 1) -> tuple[CommissionScheme, list[CommissionRuleLine]]:
    """钢贸现货: 按挂牌毛利 30%, 利润型 35%, 走量型 25%, 间销 15%."""
    scheme = CommissionScheme(
        tenant_id=tenant_id, scheme_id=scheme_id,
        scheme_code="TPL_TRADE_GP30",
        scheme_name="【模板】钢贸-按挂牌毛利30%",
        business_line="TRADE",
        base_type="LISTED_GROSS_PROFIT",
        rate_default=0.30,
        min_commission_per_month=3000.0,
        effective_from=date(2024, 1, 1),
    )
    rules = [
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=1,
            rule_label="直销+现款+利润型", priority=10,
            match_sales_mode="DIRECT", match_settle_type="CASH", match_customer_seg="PROFIT",
            rate=0.35, rate_unit="PCT"),
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=2,
            rule_label="直销+T+30+利润型", priority=20,
            match_sales_mode="DIRECT", match_settle_type="T+30", match_customer_seg="PROFIT",
            rate=0.32, rate_unit="PCT"),
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=3,
            rule_label="直销+走量型", priority=30,
            match_sales_mode="DIRECT", match_customer_seg="VOLUME",
            rate=0.25, rate_unit="PCT"),
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=4,
            rule_label="间销/转单", priority=40,
            match_sales_mode="INDIRECT",
            rate=0.15, rate_unit="PCT"),
    ]
    return scheme, rules


def process_template(tenant_id: int = 0, scheme_id: int = 2) -> tuple[CommissionScheme, list[CommissionRuleLine]]:
    """加工厂: 加工费15% + 钢材买卖 25-30%."""
    scheme = CommissionScheme(
        tenant_id=tenant_id, scheme_id=scheme_id,
        scheme_code="TPL_PROCESS_FEE15",
        scheme_name="【模板】加工-加工费15%+钢材毛利25%",
        business_line="PROCESS",
        base_type="PROCESSING_FEE",
        rate_default=0.15,
        min_commission_per_month=3500.0,
        effective_from=date(2024, 1, 1),
    )
    rules = [
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=1,
            rule_label="加工费收入", priority=10,
            rate=0.15, rate_unit="PCT"),
    ]
    return scheme, rules


def mill_template(tenant_id: int = 0, scheme_id: int = 3) -> tuple[CommissionScheme, list[CommissionRuleLine]]:
    """钢厂: 按吨毛利 50 元/吨, 不分客群."""
    scheme = CommissionScheme(
        tenant_id=tenant_id, scheme_id=scheme_id,
        scheme_code="TPL_MILL_TONNAGE",
        scheme_name="【模板】钢厂-按吨毛利元/吨",
        business_line="MILL",
        base_type="TON_GROSS_PROFIT",
        rate_default=50.0,
        use_customer_seg=False,
        use_direct_indirect=False,
        use_biz_fee_deduct=False,
        use_roundoff_deduct=False,
        use_prepay_interest=False,
        min_commission_per_month=5000.0,
        effective_from=date(2024, 1, 1),
    )
    rules = [
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=1,
            rule_label="统一", priority=10,
            rate=50.0, rate_unit="YUAN_PER_TON"),
    ]
    return scheme, rules


def shell_template(tenant_id: int = 0, scheme_id: int = 4) -> tuple[CommissionScheme, list[CommissionRuleLine]]:
    """皮包公司: 撮合差价 50%, 不收资金成本 (没库存)."""
    scheme = CommissionScheme(
        tenant_id=tenant_id, scheme_id=scheme_id,
        scheme_code="TPL_SHELL_SPREAD",
        scheme_name="【模板】皮包/纯撮合-按差价50%",
        business_line="SHELL",
        base_type="SPREAD",
        rate_default=0.50,
        ar_interest_rate=0.0, inv_interest_rate=0.0, prepay_interest_rate=0.0,
        use_ar_interest=False, use_inv_interest=False, use_prepay_interest=False,
        use_biz_fee_deduct=False, use_roundoff_deduct=False,
        min_commission_per_month=1500.0,
        effective_from=date(2024, 1, 1),
    )
    rules = [
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=1,
            rule_label="撮合直成", priority=10,
            match_sales_mode="DIRECT",
            rate=0.50, rate_unit="PCT"),
        CommissionRuleLine(tenant_id=tenant_id, scheme_id=scheme_id, rule_id=2,
            rule_label="挂单转单中介", priority=20,
            match_sales_mode="TRANSIT",
            rate=0.20, rate_unit="PCT"),
    ]
    return scheme, rules


TEMPLATES = {
    "TRADE": trade_template,
    "PROCESS": process_template,
    "MILL": mill_template,
    "SHELL": shell_template,
}


def get_template(business_line: str, tenant_id: int = 0):
    fn = TEMPLATES.get(business_line.upper())
    if not fn:
        raise ValueError(f"unknown business_line: {business_line}")
    return fn(tenant_id=tenant_id)
