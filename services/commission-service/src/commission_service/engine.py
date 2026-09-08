"""提成计算核心引擎.

设计要点:
1) 完全无副作用 -- 输入 CalcContext, 输出 CommissionResult, 不读 DB. 便于单测/复算.
2) 规则匹配按 priority 升序, 短路第一条命中.
3) 利息扣减 = 平均占用 × 适用利率 × 期间天数.
4) 直销/间销/客群系数为乘积调整 (而非加和), 透明可解释.
5) explain_trace 记录每一步, 工资条可直接展示.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Optional
from .models import (
    CalcContext, CommissionResult, CommissionRuleLine,
    CommissionLineDetail, SalesOrderInput, CommissionScheme,
)

DAYS_IN_MONTH = 30  # 简化, 全部按 30 天/月计算资金成本


def _match_rule(order: SalesOrderInput, rules: list[CommissionRuleLine]) -> Optional[CommissionRuleLine]:
    """按 priority 顺序找第一条匹配的规则.

    任一字段为空 = 该字段任意值.
    """
    for r in sorted(rules, key=lambda x: x.priority):
        if not r.is_active:
            continue
        if r.match_sales_mode and r.match_sales_mode != order.sales_mode:
            continue
        if r.match_settle_type and r.match_settle_type != order.settle_type:
            continue
        if r.match_customer_seg and r.match_customer_seg != order.customer_seg:
            continue
        if r.match_product_type and r.match_product_type != order.product_type:
            continue
        if r.match_origin_id is not None and r.match_origin_id != order.origin_id:
            continue
        if r.match_grade_family and r.match_grade_family != order.grade_family:
            continue
        if r.match_org_id is not None and r.match_org_id != order.org_id:
            continue
        # 边际毛利门槛 (按吨毛利)
        ton_gp = order.ton_gross_profit
        if r.match_min_margin is not None and ton_gp < r.match_min_margin:
            continue
        if r.match_max_margin is not None and ton_gp > r.match_max_margin:
            continue
        return r
    return None


def _direct_indirect_adj(order: SalesOrderInput, scheme: CommissionScheme) -> float:
    """直销/间销/转单 系数. 当 scheme.use_direct_indirect 关闭时返回 1.0."""
    if not scheme.use_direct_indirect:
        return 1.0
    mode = (order.sales_mode or "").upper()
    if mode in ("DIRECT", "SHELL"):
        return 1.0
    if mode == "INDIRECT":
        return 0.5
    if mode == "TRANSIT":
        return 0.3
    return 1.0


def _customer_seg_adj(order: SalesOrderInput, scheme: CommissionScheme) -> float:
    """客群差异化系数: 利润型 1.2, 走量型 0.8, 战略 1.0; 关闭则 1.0."""
    if not scheme.use_customer_seg:
        return 1.0
    seg = (order.customer_seg or "").upper()
    table = {
        "PROFIT": 1.2,
        "VOLUME": 0.8,
        "STRATEGIC": 1.0,
        "A": 1.1,
        "B": 1.0,
        "C": 0.7,
    }
    return table.get(seg, 1.0)


def _base_for_rule(order: SalesOrderInput, scheme: CommissionScheme) -> float:
    """根据 scheme.base_type 取该订单的"提成基数"."""
    bt = scheme.base_type.upper()
    if bt == "LISTED_GROSS_PROFIT":
        return order.listed_gross_profit
    if bt == "TON_GROSS_PROFIT":
        return order.ton_gross_profit * order.tonnage
    if bt == "NET_PROFIT":
        # 不在此处扣利息, 总扣减在汇总后统一做
        return order.listed_gross_profit
    if bt == "PROCESSING_FEE":
        return order.processing_fee
    if bt == "REVENUE":
        return order.revenue
    if bt == "SPREAD":
        return order.spread_per_ton * order.tonnage
    return 0.0


def _apply_rate(base: float, rule_rate: float, rate_unit: str, tonnage: float) -> float:
    if rate_unit.upper() == "YUAN_PER_TON":
        return rule_rate * tonnage
    return base * rule_rate


def calculate(ctx: CalcContext) -> CommissionResult:
    """根据 ctx 计算单个销售员单月提成.

    输出 CommissionResult, 含 explain_trace 完整审计链.
    """
    scheme = ctx.scheme
    assert scheme is not None, "scheme required"
    out = CommissionResult(
        tenant_id=ctx.tenant_id,
        period_month=ctx.period_month,
        rep_id=ctx.rep_id,
        rep_name=ctx.rep_name,
        scheme_id=scheme.scheme_id,
        scheme_code=scheme.scheme_code,
    )
    out.explain_trace.append(
        f"方案={scheme.scheme_code}({scheme.scheme_name}), 基数类型={scheme.base_type}, 默认系数={scheme.rate_default}"
    )

    raw_commission_sum = 0.0
    weighted_rate_numer = 0.0
    weighted_rate_denom = 0.0

    for od in ctx.orders:
        out.gross_profit_listed += od.listed_gross_profit
        out.gross_profit_ton += od.ton_gross_profit * od.tonnage
        out.revenue_amount += od.revenue
        out.tonnage += od.tonnage
        out.processing_fee += od.processing_fee
        out.spread_amount += od.spread_per_ton * od.tonnage
        if scheme.use_biz_fee_deduct:
            out.biz_fee_amt += od.biz_fee_amt
        if scheme.use_roundoff_deduct:
            out.roundoff_amt += od.roundoff_amt

        matched = _match_rule(od, ctx.rules)
        rate = matched.rate if matched else scheme.rate_default
        rate_unit = matched.rate_unit if matched else "PCT"
        adj_di = _direct_indirect_adj(od, scheme)
        adj_seg = _customer_seg_adj(od, scheme)

        base_one = _base_for_rule(od, scheme)
        raw = _apply_rate(base_one, rate, rate_unit, od.tonnage) * adj_di * adj_seg
        raw_commission_sum += raw

        # 用于加权平均最终系数
        if base_one > 0 and rate_unit == "PCT":
            weighted_rate_numer += rate * adj_di * adj_seg * base_one
            weighted_rate_denom += base_one

        out.line_details.append(CommissionLineDetail(
            order_no=od.order_no,
            matched_rule_id=matched.rule_id if matched else None,
            matched_rule_label=matched.rule_label if matched else "(default)",
            base_amount=base_one,
            rate=rate, rate_unit=rate_unit,
            raw_commission=raw,
            adjust_direct=adj_di,
            adjust_customer_seg=adj_seg,
        ))

    # 利息扣减: 用月平均余额 × 适用利率 × 30 天
    if scheme.use_ar_interest:
        ar_bal = sum(o.avg_ar_balance for o in ctx.orders) / max(1, len(ctx.orders))
        out.ar_interest_amt = ar_bal * scheme.ar_interest_rate * DAYS_IN_MONTH
    if scheme.use_inv_interest:
        inv_bal = sum(o.avg_inv_balance for o in ctx.orders) / max(1, len(ctx.orders))
        out.inv_interest_amt = inv_bal * scheme.inv_interest_rate * DAYS_IN_MONTH
    if scheme.use_prepay_interest:
        pp_bal = sum(o.avg_prepay_balance for o in ctx.orders) / max(1, len(ctx.orders))
        out.prepay_interest_amt = pp_bal * scheme.prepay_interest_rate * DAYS_IN_MONTH

    deductions = (out.ar_interest_amt + out.inv_interest_amt + out.prepay_interest_amt
                  + out.biz_fee_amt + out.roundoff_amt)
    out.base_amount = max(0.0, raw_commission_sum)  # base 用于工资条展示
    out.commission_calc = max(0.0, raw_commission_sum - deductions)

    if weighted_rate_denom > 0:
        out.rate_effective = weighted_rate_numer / weighted_rate_denom

    out.explain_trace.append(
        f"原始提成总额={raw_commission_sum:.2f}, 应收利息扣减={out.ar_interest_amt:.2f}, "
        f"库存利息={out.inv_interest_amt:.2f}, 预付利息={out.prepay_interest_amt:.2f}, "
        f"业务费扣={out.biz_fee_amt:.2f}, 抹零扣={out.roundoff_amt:.2f}"
    )

    # 兜底 / 封顶
    out.commission_floor = scheme.min_commission_per_month
    out.commission_cap = scheme.max_commission_per_month
    final_v = out.commission_calc
    if out.commission_floor is not None and final_v < out.commission_floor:
        final_v = out.commission_floor
        out.explain_trace.append(f"低于保底 {out.commission_floor:.2f}, 拉到保底")
    if out.commission_cap is not None and final_v > out.commission_cap:
        final_v = out.commission_cap
        out.explain_trace.append(f"超过封顶 {out.commission_cap:.2f}, 拉到封顶")
    out.commission_final = round(final_v, 2)
    return out
