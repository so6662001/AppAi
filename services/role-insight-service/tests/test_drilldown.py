"""钻取推荐 + 归因 测试."""
from __future__ import annotations
import pytest
from role_insight.drilldown import recommend_paths, attribute_change


def test_recommend_paths_sales_amount():
    p = recommend_paths("sales_amount")
    assert p.metric_code == "sales_amount"
    assert len(p.paths) >= 4
    codes = [x["dim_code"] for x in p.paths]
    assert "customer" in codes
    assert "product_type" in codes

def test_recommend_paths_unknown():
    p = recommend_paths("unknown_metric")
    assert p.paths == []

def test_attribute_simple_growth():
    """销售额本期 100 比上期 80 涨 25%, 客户 A 贡献最大."""
    res = attribute_change(
        metric_code="sales_amount",
        metric_label="销售额",
        current=100, previous=80,
        breakdown=[
            {"dim_value":"客户A", "current":50, "previous":30, "contribution": 20},
            {"dim_value":"客户B", "current":30, "previous":25, "contribution": 5},
            {"dim_value":"客户C", "current":20, "previous":25, "contribution": -5},
        ],
    )
    assert res.delta_abs == 20
    assert res.delta_pct == pytest.approx(0.25)
    # Top 1 = 客户A (按绝对贡献)
    assert res.top_contributors[0]["dim_value"] == "客户A"
    assert "增长" in res.summary_text
    assert len(res.suggested_actions) >= 1

def test_attribute_drop():
    res = attribute_change(
        metric_code="ton_gross_profit",
        metric_label="吨毛利",
        current=160, previous=200,
        breakdown=[
            {"dim_value":"螺纹钢", "current":100, "previous":140, "contribution":-40},
            {"dim_value":"热卷板", "current": 60, "previous": 60, "contribution":  0},
        ],
    )
    assert res.delta_abs == -40
    assert res.delta_pct == pytest.approx(-0.2)
    assert "下降" in res.summary_text

def test_attribute_no_breakdown():
    res = attribute_change(
        metric_code="x", metric_label="X", current=10, previous=None, breakdown=[],
    )
    assert res.delta_abs is None
    assert res.top_contributors == []
