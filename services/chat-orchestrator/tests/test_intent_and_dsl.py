"""意图识别 + DSL 构造测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chat_orchestrator.intent import detect
from chat_orchestrator.dsl_builder import build_dsl


# 模拟 registry 同义词
SYNS = ["销售额", "营收", "毛利", "吨毛利", "达交率", "OEE", "库存吨数"]
MAP = {
    "销售额": "sales_amount", "营收": "sales_amount",
    "毛利": "gross_profit", "吨毛利": "ton_gross_profit",
    "达交率": "on_time_delivery_rate",
    "OEE": "oee",
    "库存吨数": "inv_tonnage",
}


def test_basic_intent():
    i = detect("昨天我们的销售额", SYNS)
    assert i.type == "REPORT"
    assert "销售额" in i.metrics_keywords
    assert i.time_preset == "yesterday"


def test_drill_intent():
    i = detect("上周华东达交率为什么下降", SYNS)
    assert i.type == "DRILL"
    assert "达交率" in i.metrics_keywords
    assert "华东" in i.raw_text


def test_dimension_extracted():
    i = detect("按客户的吨毛利 Top10", SYNS)
    assert "customer" in i.dimensions
    assert i.top_n == 10
    assert "吨毛利" in i.metrics_keywords


def test_compare_extracted():
    i = detect("本月销售额同比", SYNS)
    assert i.compare == "yoy"
    assert i.time_preset == "mtd"


def test_origin_dimension():
    i = detect("按产地拆解上月销售额", SYNS)
    assert "origin.origin_name" in i.dimensions
    assert "销售额" in i.metrics_keywords
    assert i.time_preset == "last_month"


def test_dsl_build_default_to_sales_amount():
    i = detect("帮我看看", SYNS)
    dsl = build_dsl(i, MAP)
    assert dsl["metrics"] == ["sales_amount"]
    assert dsl["time"]["preset"] == "yesterday"


def test_dsl_topn():
    i = detect("按客户的吨毛利 Top5", SYNS)
    dsl = build_dsl(i, MAP)
    assert dsl["metrics"] == ["ton_gross_profit"]
    assert dsl["dimensions"] == ["customer"]
    assert dsl["topN"]["n"] == 5
    assert dsl["orderBy"][0]["dir"] == "desc"


def test_dsl_compare_wow():
    i = detect("上周销售额周环比", SYNS)
    dsl = build_dsl(i, MAP)
    assert dsl["compare"]["mode"] == "wow"


def test_dsl_metrics_dedup_and_limit():
    """识别 4+ 个指标时限制最多 4 个."""
    i = detect("销售额 毛利 吨毛利 达交率 OEE 库存吨数", SYNS)
    dsl = build_dsl(i, MAP)
    assert len(dsl["metrics"]) <= 4


def test_dsl_filter_passthrough():
    i = detect("昨天的销售额", SYNS)
    i.filters = [{"field": "org.region", "op": "=", "value": "华东"}]
    dsl = build_dsl(i, MAP)
    assert dsl["filters"][0]["value"] == "华东"
