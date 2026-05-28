"""提成引擎核心逻辑测试 - 钢贸/加工/钢厂/皮包 4 套."""
from __future__ import annotations
from datetime import date
import pytest

from commission_service.models import (
    CalcContext, CommissionScheme, CommissionRuleLine, SalesOrderInput,
)
from commission_service.engine import calculate
from commission_service.templates import trade_template, process_template, mill_template, shell_template


# ---------- 钢贸模板 ----------

def test_trade_profit_customer_direct_cash():
    """直销+现款+利润型 → 35% 系数 × 客群1.2 × 直销1.0."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO001", order_date=date(2026,5,1),
        rep_id=100, customer_id=1, customer_seg="PROFIT",
        sales_mode="DIRECT", settle_type="CASH",
        tonnage=100, revenue=400000, cost=380000,
        listed_gross_profit=20000, ton_gross_profit=200,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    # 命中规则 #1, rate=0.35, 客群 PROFIT=1.2, 直销=1.0
    expected_raw = 20000 * 0.35 * 1.0 * 1.2  # = 8400
    assert r.line_details[0].matched_rule_id == 1
    assert abs(r.line_details[0].raw_commission - expected_raw) < 0.01
    assert r.gross_profit_listed == 20000
    # 没有应收/库存/预付占用 → 仅原始毛利系数
    assert r.commission_calc == pytest.approx(expected_raw, 0.01)


def test_trade_volume_customer_t30():
    """走量型 + T+30, 系数 0.25 × 客群 VOLUME=0.8 × 直销=1.0 = 0.20."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO002", order_date=date(2026,5,2),
        rep_id=100, customer_id=2, customer_seg="VOLUME",
        sales_mode="DIRECT", settle_type="T+30",
        tonnage=200, revenue=800000, cost=780000,
        listed_gross_profit=20000, ton_gross_profit=100,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert r.line_details[0].matched_rule_id == 3   # 直销+走量型
    expected = 20000 * 0.25 * 0.8 * 1.0  # 4000
    assert abs(r.line_details[0].raw_commission - expected) < 0.01


def test_trade_indirect():
    """间销 → 15%, 直销系数 0.5."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO003", order_date=date(2026,5,3),
        rep_id=100, customer_id=3, customer_seg="VOLUME",
        sales_mode="INDIRECT", settle_type="T+60",
        tonnage=50, revenue=200000, cost=190000,
        listed_gross_profit=10000, ton_gross_profit=200,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert r.line_details[0].matched_rule_id == 4
    expected = 10000 * 0.15 * 0.5 * 0.8  # indirect=0.5 volume=0.8 = 600
    assert abs(r.line_details[0].raw_commission - expected) < 0.01


def test_trade_with_ar_interest():
    """有应收占用 → 提成扣息."""
    scheme, rules = trade_template(tenant_id=1)
    # 100 万应收, 0.0125%/天, 30 天 ≈ 3750 元
    od = SalesOrderInput(
        order_no="SO004", order_date=date(2026,5,1),
        rep_id=100, customer_id=1, customer_seg="PROFIT",
        sales_mode="DIRECT", settle_type="CASH",
        tonnage=100, revenue=400000, cost=380000,
        listed_gross_profit=20000, ton_gross_profit=200,
        avg_ar_balance=1_000_000,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert r.ar_interest_amt == pytest.approx(1_000_000 * 0.000125 * 30)   # 3750
    # 8400 - 3750 = 4650
    assert r.commission_calc == pytest.approx(8400 - 3750, 0.01)


def test_trade_floor():
    """业绩太低 → 拉到保底 3000."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO005", order_date=date(2026,5,1),
        rep_id=100, customer_id=1, customer_seg="VOLUME",
        sales_mode="DIRECT", settle_type="CASH",
        tonnage=1, revenue=4000, cost=3990, listed_gross_profit=10, ton_gross_profit=10,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert r.commission_final == 3000


def test_trade_biz_fee_deduct():
    """业务费 + 抹零纳入扣减."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO006", order_date=date(2026,5,1),
        rep_id=100, customer_id=1, customer_seg="PROFIT",
        sales_mode="DIRECT", settle_type="CASH",
        tonnage=100, revenue=400000, cost=380000,
        listed_gross_profit=20000, ton_gross_profit=200,
        biz_fee_amt=500, roundoff_amt=80,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    # 原始 8400 - 业务费 500 - 抹零 80 = 7820
    assert r.commission_calc == pytest.approx(8400 - 500 - 80, 0.01)


# ---------- 加工厂 ----------

def test_process_template_processing_fee():
    """加工费 100k × 15% = 15000."""
    scheme, rules = process_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO101", order_date=date(2026,5,1),
        rep_id=200, customer_id=1, customer_seg="STRATEGIC",
        sales_mode="DIRECT", settle_type="T+30",
        tonnage=500, revenue=2000000, processing_fee=100000,
        listed_gross_profit=0, ton_gross_profit=0,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=200, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    # PROCESSING_FEE 基数 100k × 15% × 直销 1.0 × 战略 1.0 = 15000
    assert r.commission_calc == pytest.approx(15000, 0.01)


# ---------- 钢厂 ----------

def test_mill_template_yuan_per_ton():
    """钢厂 每吨 50 元 × 1000 吨 = 50000, 不分客群."""
    scheme, rules = mill_template(tenant_id=1)
    assert scheme.use_customer_seg is False
    od = SalesOrderInput(
        order_no="SO201", order_date=date(2026,5,1),
        rep_id=300, customer_id=1, customer_seg="VOLUME",
        sales_mode="INDIRECT",      # 钢厂不区分直销/间销
        tonnage=1000, revenue=4_000_000, ton_gross_profit=80,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=300, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert r.commission_calc == pytest.approx(50 * 1000, 0.01)  # 50 元/吨


# ---------- 皮包公司 ----------

def test_shell_template_spread():
    """皮包公司: 撮合差价 50 元/吨 × 500 吨 × 50% = 12500."""
    scheme, rules = shell_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO301", order_date=date(2026,5,1),
        rep_id=400, customer_id=1, customer_seg="PROFIT",
        sales_mode="DIRECT", settle_type="CASH",
        tonnage=500, spread_per_ton=50, revenue=2_000_000,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=400, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    # base=50*500=25000, rate=0.5, 客群PROFIT=1.2, 直销=1.0 = 15000
    # 但 SHELL 关了 customer_seg? 没有, shell 默认 use_customer_seg=True
    assert r.commission_calc == pytest.approx(25000 * 0.5 * 1.2 * 1.0, 0.01)


def test_shell_transit_lower_rate():
    """皮包公司挂单转单 → 20%."""
    scheme, rules = shell_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO302", order_date=date(2026,5,1),
        rep_id=400, customer_id=1, customer_seg="VOLUME",
        sales_mode="TRANSIT", settle_type="CASH",
        tonnage=500, spread_per_ton=50, revenue=2_000_000,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=400, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    # 命中规则#2, rate=0.20, transit 系数 0.3, customer VOLUME=0.8 → 1200, 低于保底 1500
    expected_raw = 25000 * 0.20 * 0.3 * 0.8
    assert r.commission_calc == pytest.approx(expected_raw, 0.01)
    assert r.commission_final == 1500.0   # 保底拉起


def test_explain_trace_present():
    """explain_trace 必须可读, 工资条会显示."""
    scheme, rules = trade_template(tenant_id=1)
    od = SalesOrderInput(
        order_no="SO007", order_date=date(2026,5,1), rep_id=100, customer_id=1,
        customer_seg="PROFIT", sales_mode="DIRECT", settle_type="CASH",
        tonnage=100, revenue=400000, listed_gross_profit=20000, ton_gross_profit=200,
    )
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=100, scheme=scheme, rules=rules, orders=[od])
    r = calculate(ctx)
    assert len(r.explain_trace) >= 2
    assert "方案" in r.explain_trace[0]
    assert "TPL_TRADE_GP30" in r.explain_trace[0]


def test_multiple_orders_aggregate():
    """多单聚合: 总毛利 / 多条规则命中并加权."""
    scheme, rules = trade_template(tenant_id=1)
    orders = [
        SalesOrderInput(order_no="A", order_date=date(2026,5,1), rep_id=1, customer_id=1,
            customer_seg="PROFIT", sales_mode="DIRECT", settle_type="CASH",
            tonnage=100, listed_gross_profit=20000, ton_gross_profit=200),
        SalesOrderInput(order_no="B", order_date=date(2026,5,2), rep_id=1, customer_id=2,
            customer_seg="VOLUME", sales_mode="DIRECT", settle_type="T+30",
            tonnage=200, listed_gross_profit=20000, ton_gross_profit=100),
        SalesOrderInput(order_no="C", order_date=date(2026,5,3), rep_id=1, customer_id=3,
            customer_seg="VOLUME", sales_mode="INDIRECT", settle_type="T+60",
            tonnage=50,  listed_gross_profit=10000, ton_gross_profit=200),
    ]
    ctx = CalcContext(tenant_id=1, period_month="2026-05", rep_id=1, scheme=scheme, rules=rules, orders=orders)
    r = calculate(ctx)
    assert r.gross_profit_listed == 50000
    assert r.tonnage == 350
    assert len(r.line_details) == 3
    # A: 8400, B: 4000, C: 600
    assert r.commission_calc == pytest.approx(8400+4000+600, 0.01)
