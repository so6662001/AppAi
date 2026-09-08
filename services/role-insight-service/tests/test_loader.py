"""YAML loader 测试."""
from __future__ import annotations
import os
from pathlib import Path
import pytest

from role_insight import loader


def setup_module():
    os.environ["ROLE_INSIGHTS_DIR"] = "/workspace/role_insights"
    loader.PROFILE_DIR = Path("/workspace/role_insights")


def test_load_all_returns_six_or_more():
    profiles = loader.load_all()
    assert len(profiles) >= 7   # 现共 7+ 个岗位 (含销售部经理 + 采购经理)


def test_get_profile_sales_mgr():
    p = loader.get_profile("TRADE_SALES_MGR")
    assert p is not None
    assert p.role_name == "销售部经理"
    assert p.level == "MANAGER"
    assert len(p.rules) >= 5


def test_get_profile_purchasing_mgr():
    p = loader.get_profile("TRADE_PURCHASING_MGR")
    assert p is not None
    assert p.role_name == "采购经理"
    assert len(p.primary_kpis) >= 6
    assert len(p.rules) >= 6


def test_get_profile_trade_owner():
    p = loader.get_profile("TRADE_OWNER")
    assert p is not None
    assert p.role_name == "钢贸老板"
    assert p.business_line == "TRADE"
    assert len(p.primary_kpis) >= 5
    assert len(p.rules) >= 3
    # weight 总和近似 1.0
    s = sum(k.weight for k in p.primary_kpis)
    assert 0.9 <= s <= 1.1


def test_get_profile_sales_rep_rules_have_actions():
    p = loader.get_profile("TRADE_SALES_REP")
    assert p is not None
    # 至少 5 条规则
    assert len(p.rules) >= 5
    # 每条规则必有 actions
    for r in p.rules:
        assert len(r.actions) >= 1


def test_get_profile_unknown():
    p = loader.get_profile("UNKNOWN_ROLE")
    assert p is None
