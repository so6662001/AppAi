"""渲染器 (rows + dsl → blocks + summary) 测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chat_orchestrator.renderer import render


def test_render_empty():
    blocks, summary = render([], {"metrics": ["sales_amount"]})
    assert blocks == []
    assert "无数据" in summary


def test_render_kpi_only():
    rows = [{"sales_amount": 18200000.0}]
    dsl = {"metrics": ["sales_amount"], "dimensions": [], "time": {"preset": "yesterday"}}
    blocks, summary = render(rows, dsl)
    assert blocks[0]["type"] == "kpi"
    assert blocks[0]["kpis"][0]["value"] == 18200000.0
    assert "万" in summary or "亿" in summary


def test_render_table_chart_for_multi_rows():
    rows = [
        {"region": "华东", "sales_amount": 18200000.0},
        {"region": "华南", "sales_amount":  8900000.0},
    ]
    dsl = {"metrics": ["sales_amount"], "dimensions": ["org.region"],
           "time": {"preset": "last_week"}}
    blocks, summary = render(rows, dsl)
    types = [b["type"] for b in blocks]
    assert "table" in types
    assert "chart" in types


def test_render_chart_for_time_series():
    rows = [
        {"biz_date": "2026-05-01", "sales_amount": 1000000},
        {"biz_date": "2026-05-02", "sales_amount": 1100000},
        {"biz_date": "2026-05-03", "sales_amount":  950000},
    ]
    dsl = {"metrics": ["sales_amount"], "dimensions": [],
           "time": {"preset": "rolling_7d", "grain": "day"}}
    blocks, summary = render(rows, dsl)
    chart = [b for b in blocks if b["type"] == "chart"]
    assert chart and chart[0]["chart"] == "line"


def test_render_format_inference():
    rows = [{"on_time_delivery_rate": 0.823}]
    dsl = {"metrics": ["on_time_delivery_rate"], "dimensions": [], "time": {"preset": "yesterday"}}
    blocks, _ = render(rows, dsl)
    assert blocks[0]["kpis"][0]["format"] == "percent"
