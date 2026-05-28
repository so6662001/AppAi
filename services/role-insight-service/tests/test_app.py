"""HTTP API 测试."""
from __future__ import annotations
import os
from pathlib import Path

os.environ["ROLE_INSIGHTS_DIR"] = "/workspace/role_insights"

from fastapi.testclient import TestClient
from role_insight import loader

loader.PROFILE_DIR = Path("/workspace/role_insights")
loader.load_all()

from role_insight.app import app
client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200


def test_list_roles():
    r = client.get("/v1/roles")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 5
    codes = [x["role_code"] for x in data]
    assert "TRADE_OWNER" in codes
    assert "TRADE_SALES_REP" in codes


def test_get_role_detail():
    r = client.get("/v1/roles/TRADE_SALES_REP")
    assert r.status_code == 200
    d = r.json()
    assert d["role_name"] == "钢贸销售员"


def test_get_role_unknown():
    r = client.get("/v1/roles/NOT_EXIST")
    assert r.status_code == 404


def test_drilldown_paths():
    r = client.get("/v1/drilldown/sales_amount/paths")
    assert r.status_code == 200
    d = r.json()
    assert d["metric_code"] == "sales_amount"
    assert len(d["paths"]) >= 4


def test_drilldown_attribute():
    r = client.post("/v1/drilldown/attribute", json={
        "metric_code": "sales_amount",
        "metric_label": "销售额",
        "current": 100, "previous": 80,
        "breakdown": [
            {"dim_value":"A","current":50,"previous":30,"contribution":20},
            {"dim_value":"B","current":50,"previous":50,"contribution":0},
        ],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["delta_abs"] == 20
    assert d["top_contributors"][0]["dim_value"] == "A"


def test_diagnose_endpoint():
    r = client.post("/v1/diagnose", json={
        "tenant_id": 1, "user_id": 200237,
        "role_code": "TRADE_SALES_REP",
        "period_month": "2026-05",
        "kpi_values": {
            "my_ton_gross_profit": 156, "my_active_customers": 8,
            "my_ar_balance": 1_800_000, "my_aged_ar_pct": 0.18,
            "my_commission_calc": 18720, "my_new_customer_count": 2,
            "team_avg_ton_gross_profit": 186,
            "top2_customer_share": 0.74,
            "indirect_share": 0.45,
            "my_tonnage_mom_pct": -0.25,
        },
        "benchmarks": {
            "my_ton_gross_profit": {"p25":120,"p50":165,"p75":215,"top10":280,"direction":"HIGHER"}
        },
        "peer_avgs": {},
        "extras": {
            "gap_pct": 0.16, "potential": 13800, "team_avg": 186,
            "my_aged_ar": 280_000, "risk_amount": 84000,
            "top1_name":"客户A", "top1_pct":0.42, "top2_share":0.74,
            "commission_loss": 4200, "peer_avg": 2.4,
        },
    })
    assert r.status_code == 200, r.text
    d = r.json()
    # 触发了 TGP < 团队均值 0.85
    assert d["finding_count"] >= 1
    assert d["health_score"] <= 80
    assert len(d["top_actions"]) <= 3


def test_demo_snapshot_sales_rep():
    r = client.get("/v1/demo/snapshot/TRADE_SALES_REP")
    assert r.status_code == 200
    d = r.json()
    assert d["role_code"] == "TRADE_SALES_REP"
    assert d["finding_count"] >= 3
    assert d["high_count"] >= 1
    assert len(d["top_actions"]) <= 3
    # 雷达图数据
    assert len(d["kpi_radar"]) >= 5


def test_demo_snapshot_owner():
    r = client.get("/v1/demo/snapshot/TRADE_OWNER")
    assert r.status_code == 200
    d = r.json()
    assert d["finding_count"] >= 3


def test_demo_snapshot_finance():
    r = client.get("/v1/demo/snapshot/FINANCE_CTRL")
    assert r.status_code == 200
    d = r.json()
    assert d["finding_count"] >= 2
