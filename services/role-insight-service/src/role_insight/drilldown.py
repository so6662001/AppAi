"""指标钻取 - 推荐路径 + AI 归因 (对接 dsl-compiler + query-engine)."""
from __future__ import annotations
import os
import logging
from typing import Optional

from .models import DrilldownPath, DrilldownAttribution, ActionItem

log = logging.getLogger("drilldown")

# 默认钻取路径 (与 ddl/21_role_insight.sql 中 metric_drilldown_path 一致)
DEFAULT_PATHS = {
    "sales_amount": [
        {"order":1, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar",     "topn":10,
         "ai_prompt":"按客户拆: Top {topn} 占比 {topn_share:.0%}, 是否过于集中?"},
        {"order":2, "dim_code":"product_type", "dim_label":"产品类型", "viz":"pie",     "topn":10,
         "ai_prompt":"按产品: 主营 {top_product} 占 {top_share:.0%}, 结构是否健康?"},
        {"order":3, "dim_code":"origin",       "dim_label":"产地",     "viz":"treemap", "topn":10,
         "ai_prompt":"按产地: 哪个钢厂系贡献最大"},
        {"order":4, "dim_code":"region",       "dim_label":"区域",     "viz":"bar",     "topn":10,
         "ai_prompt":"按区域: 华东/华北/华南"},
        {"order":5, "dim_code":"rep_id",       "dim_label":"销售员",   "viz":"bar",     "topn":15,
         "ai_prompt":"按销售员: 业绩分布是否均衡"},
    ],
    "ton_gross_profit": [
        {"order":1, "dim_code":"product_type", "dim_label":"产品类型", "viz":"bar", "topn":8,
         "ai_prompt":"哪个产品毛利好/差?"},
        {"order":2, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar", "topn":10,
         "ai_prompt":"Top 利润客户; 是否被走量客户拉低?"},
        {"order":3, "dim_code":"origin",       "dim_label":"产地",     "viz":"bar", "topn":10,
         "ai_prompt":"哪些产地高溢价能力?"},
        {"order":4, "dim_code":"rep_id",       "dim_label":"销售员",   "viz":"bar", "topn":15,
         "ai_prompt":"哪些销售员高毛利? 学他玩法"},
    ],
    "capital_occupation": [
        {"order":1, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar", "topn":15,
         "ai_prompt":"Top 占资金客户 + IRR 评级"},
        {"order":2, "dim_code":"rep_id",       "dim_label":"销售员",   "viz":"bar", "topn":15,
         "ai_prompt":"哪些销售员占资金过多?"},
        {"order":3, "dim_code":"aging_band",   "dim_label":"账龄段",   "viz":"bar", "topn":6,
         "ai_prompt":"0-30/31-60/61-90/91-180/180+ 分布"},
    ],
    "inv_amount": [
        {"order":1, "dim_code":"origin",       "dim_label":"产地",     "viz":"treemap","topn":10,
         "ai_prompt":"哪个钢厂系库存最大?"},
        {"order":2, "dim_code":"product_type", "dim_label":"产品",     "viz":"bar",    "topn":10,
         "ai_prompt":"什么产品压货多?"},
        {"order":3, "dim_code":"aging_band",   "dim_label":"库龄",     "viz":"bar",    "topn":6,
         "ai_prompt":"0-30/31-60/61-90/91-180/180+"},
        {"order":4, "dim_code":"warehouse",    "dim_label":"仓库",     "viz":"bar",    "topn":8,
         "ai_prompt":"哪个仓压货多?"},
    ],
    "ar_amount": [
        {"order":1, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar", "topn":15,
         "ai_prompt":"Top 应收客户"},
        {"order":2, "dim_code":"aging_band",   "dim_label":"账龄",     "viz":"bar", "topn":6,
         "ai_prompt":"账龄分布健康度"},
        {"order":3, "dim_code":"rep_id",       "dim_label":"销售员",   "viz":"bar", "topn":15,
         "ai_prompt":"哪些销售员应收最多?"},
    ],
    "biz_fee_total": [
        {"order":1, "dim_code":"rep_id",       "dim_label":"销售员",   "viz":"bar", "topn":15,
         "ai_prompt":"业务费 Top 销售员"},
        {"order":2, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar", "topn":10,
         "ai_prompt":"业务费 Top 客户"},
        {"order":3, "dim_code":"reason_code",  "dim_label":"事由",     "viz":"pie", "topn":8,
         "ai_prompt":"业务费用途分布"},
    ],
    "net_profit": [
        {"order":1, "dim_code":"entity_id",    "dim_label":"主体",     "viz":"bar", "topn":8,
         "ai_prompt":"哪个主体最赚/最亏?"},
        {"order":2, "dim_code":"product_type", "dim_label":"产品",     "viz":"bar", "topn":10,
         "ai_prompt":"哪个产品贡献利润?"},
        {"order":3, "dim_code":"customer",     "dim_label":"客户",     "viz":"bar", "topn":15,
         "ai_prompt":"哪些客户贡献利润?"},
    ],
    "ccc_days": [
        {"order":1, "dim_code":"composition",  "dim_label":"CCC 构成", "viz":"waterfall", "topn":4,
         "ai_prompt":"库存周转 + 应收周转 - 应付周转, 哪段拉长?"},
        {"order":2, "dim_code":"entity_id",    "dim_label":"主体",     "viz":"bar",       "topn":8,
         "ai_prompt":"哪个主体 CCC 最长?"},
    ],
}


def recommend_paths(metric_code: str) -> DrilldownPath:
    paths = DEFAULT_PATHS.get(metric_code, [])
    return DrilldownPath(metric_code=metric_code, paths=paths)


def attribute_change(
    metric_code: str,
    metric_label: str,
    current: float,
    previous: Optional[float],
    breakdown: list[dict],   # [{dim_value, current, previous, contribution}]
    period: str = "本期 vs 上期",
) -> DrilldownAttribution:
    """根据维度拆分计算归因 - 找出 Top 贡献项."""
    delta_abs = (current - previous) if previous is not None else None
    delta_pct = ((current / previous - 1.0) if previous else None) if previous else None

    # 找 Top 5 贡献 (按 contribution 绝对值)
    sorted_b = sorted(breakdown, key=lambda x: abs(x.get("contribution", 0)), reverse=True)[:5]
    top = [{
        "dim_value": x.get("dim_value", "?"),
        "current":   x.get("current"),
        "previous":  x.get("previous"),
        "contribution": x.get("contribution"),
        "share":     (x.get("contribution") / delta_abs if delta_abs else 0),
    } for x in sorted_b]

    # 生成中文归因摘要
    direction = "增长" if (delta_abs or 0) > 0 else ("下降" if (delta_abs or 0) < 0 else "持平")
    if top and delta_abs:
        top_str = ", ".join(f"{t['dim_value']} 贡献 {abs((t['share'] or 0)):.0%}" for t in top[:3])
        summary = f"{metric_label} {period} {direction} {abs(delta_abs):,.0f} ({delta_pct:+.1%}), 主要来自: {top_str}"
    else:
        summary = f"{metric_label} {period} {direction}"

    return DrilldownAttribution(
        metric_code=metric_code,
        metric_label=metric_label,
        period=period,
        current=current,
        previous=previous,
        delta_abs=delta_abs,
        delta_pct=delta_pct,
        top_contributors=top,
        summary_text=summary,
        suggested_actions=[
            ActionItem(label="跟 AI 深入聊聊", type="chat", prompt=f"{metric_label}为什么{direction}? 给具体建议"),
            ActionItem(label="导出 Excel",     type="action", handler="exportExcel"),
        ],
    )
