"""commission-service HTTP 端点测试."""
from __future__ import annotations
from datetime import date
from fastapi.testclient import TestClient

from commission_service.app import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_list_templates():
    r = client.get("/v1/templates")
    assert r.status_code == 200
    keys = r.json().keys()
    assert {"TRADE", "PROCESS", "MILL", "SHELL"} <= set(keys)


def test_get_one_template_trade():
    r = client.get("/v1/templates/TRADE")
    assert r.status_code == 200
    data = r.json()
    assert data["scheme"]["scheme_code"] == "TPL_TRADE_GP30"
    assert len(data["rules"]) == 4


def test_get_one_template_unknown():
    r = client.get("/v1/templates/UNKNOWN")
    assert r.status_code == 400


def test_calc_by_template_shell():
    """皮包: 撮合差价 50 元 × 500 吨 × 50% rate × 1.2 PROFIT 系数."""
    payload = {
        "business_line": "SHELL",
        "tenant_id": 1,
        "period_month": "2026-05",
        "rep_id": 9,
        "rep_name": "张三",
        "orders": [{
            "order_no": "X1",
            "order_date": "2026-05-01",
            "rep_id": 9,
            "customer_id": 1,
            "customer_seg": "PROFIT",
            "sales_mode": "DIRECT",
            "settle_type": "CASH",
            "tonnage": 500, "spread_per_ton": 50,
            "revenue": 2000000,
        }],
    }
    r = client.post("/v1/calc/by-template", params={
        "business_line": "SHELL", "tenant_id": 1, "period_month": "2026-05",
        "rep_id": 9, "rep_name": "张三",
    }, json=payload["orders"])
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    assert result["scheme_code"] == "TPL_SHELL_SPREAD"
    assert result["commission_calc"] > 0


def test_calc_endpoint_with_full_payload():
    """v1/calc 接受方案 + 规则 + 订单全量, 用于"已配置好规则"的租户."""
    payload = {
        "tenant_id": 1, "period_month": "2026-05",
        "rep_id": 7, "rep_name": "李四",
        "scheme": {
            "tenant_id": 1, "scheme_id": 99,
            "scheme_code": "CUSTOM_TEST", "scheme_name": "测试方案",
            "business_line": "TRADE",
            "base_type": "LISTED_GROSS_PROFIT",
            "rate_default": 0.30,
            "ar_interest_rate": 0.000125,
            "inv_interest_rate": 0.000150,
            "prepay_interest_rate": 0.000125,
            "use_ar_interest": True, "use_inv_interest": True, "use_prepay_interest": True,
            "use_customer_seg": True, "use_direct_indirect": True,
            "use_biz_fee_deduct": True, "use_roundoff_deduct": True,
            "effective_from": "2024-01-01",
            "status": "ACTIVE",
        },
        "rules": [],
        "orders": [{
            "order_no": "Y1", "order_date": "2026-05-01",
            "rep_id": 7, "customer_id": 1,
            "customer_seg": "PROFIT", "sales_mode": "DIRECT", "settle_type": "CASH",
            "tonnage": 100, "revenue": 400000,
            "listed_gross_profit": 20000, "ton_gross_profit": 200,
        }],
    }
    r = client.post("/v1/calc", json=payload)
    assert r.status_code == 200, r.text
    result = r.json()["result"]
    # 没有 rules → 走 rate_default 0.3, 客群 1.2, 直销 1.0 → 7200
    assert abs(result["commission_calc"] - 7200) < 0.01
