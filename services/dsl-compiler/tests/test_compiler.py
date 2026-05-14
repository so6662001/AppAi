"""DSL 编译器单元测试。"""
from __future__ import annotations
from datetime import date
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsl_compiler.compiler import DSLCompiler
from dsl_compiler.models import DSL, DSLTime, DSLFilter, DSLCompare, CompileContext, MetricDef, CompileError
from dsl_compiler.registry import MetricRegistry, load_registry


METRICS_DIR = ROOT.parents[1] / "metrics"


@pytest.fixture(scope="module")
def registry() -> MetricRegistry:
    return load_registry(METRICS_DIR)


@pytest.fixture(scope="module")
def compiler(registry):
    return DSLCompiler(registry)


@pytest.fixture
def ctx_trade():
    return CompileContext(tenant_id=1, user_id=10, business_line="TRADE",
                          scopes=["sales.read"], visible_org_ids=[100, 101])


# ============= 加载测试 =============

def test_registry_loaded(registry):
    assert len(registry) >= 100, "至少加载 100 个指标"


def test_synonym_match(registry):
    m = registry.get("营收")
    assert m is not None
    assert m.name == "sales_amount"


def test_code_match(registry):
    m = registry.get("M001")
    assert m is not None and m.name == "sales_amount"


# ============= 基础编译 =============

def test_simple_compile(compiler, ctx_trade):
    dsl = DSL(
        metrics=["sales_amount"],
        dimensions=["org.region"],
        time=DSLTime(preset="last_week", grain="day"),
    )
    r = compiler.compile(dsl, ctx_trade)
    assert "sales_amount" in r.sql
    assert "tenant_id" in r.sql
    assert "BETWEEN" in r.sql
    assert "LIMIT 1000" in r.sql
    assert r.biz_token_estimate > 0


def test_synonym_compile(compiler, ctx_trade):
    dsl = DSL(metrics=["营收"], time=DSLTime(preset="yesterday", grain="day"))
    r = compiler.compile(dsl, ctx_trade)
    assert "sales_amount" in r.metrics_expanded


def test_tenant_injection(compiler, ctx_trade):
    dsl = DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"))
    r = compiler.compile(dsl, ctx_trade)
    assert "tenant_id" in r.sql
    assert any(v == 1 for v in r.params.values())


# ============= 业务类型裁剪 =============

def test_not_applicable_metric(compiler):
    # 出钢量只适用 MILL
    ctx = CompileContext(tenant_id=1, user_id=1, business_line="TRADE")
    with pytest.raises(CompileError) as ei:
        compiler.compile(
            DSL(metrics=["melt_tonnage"], time=DSLTime(preset="last_month")),
            ctx,
        )
    assert ei.value.code == "E_NOT_APPLICABLE"


# ============= 半累积语义 =============

def test_snapshot_avg(compiler, ctx_trade):
    dsl = DSL(
        metrics=["daily_inv_tonnage"],
        time=DSLTime(preset="last_month", grain="month"),
    )
    r = compiler.compile(dsl, ctx_trade)
    # 应该用 CTE 包一层
    assert "daily AS" in r.sql.lower() or "with " in r.sql.lower()
    assert "AVG" in r.sql


# ============= 派生指标展开 =============

def test_required_metrics_expanded(compiler, ctx_trade):
    dsl = DSL(metrics=["contribution_margin"], time=DSLTime(preset="last_month"))
    r = compiler.compile(dsl, ctx_trade)
    assert "gross_profit" in r.metrics_expanded
    assert "contribution_margin" in r.metrics_expanded


# ============= 比较模式 =============

def test_compare_wow(compiler, ctx_trade):
    dsl = DSL(
        metrics=["sales_amount"],
        dimensions=["org.region"],
        time=DSLTime(preset="last_week", grain="day"),
        compare=DSLCompare(mode="wow"),
    )
    r = compiler.compile(dsl, ctx_trade)
    assert "UNION ALL" in r.sql
    assert "_PREV" in r.sql


# ============= 过滤条件 =============

def test_filter_in_clause(compiler, ctx_trade):
    dsl = DSL(
        metrics=["sales_amount"],
        filters=[DSLFilter(field="org.region", op="in", value=["华东", "华南"])],
        time=DSLTime(preset="last_month"),
    )
    r = compiler.compile(dsl, ctx_trade)
    assert "IN (" in r.sql
    assert "华东" in r.params.values() or any(v == "华东" for v in r.params.values())


def test_filter_invalid_op(compiler, ctx_trade):
    with pytest.raises(CompileError) as ei:
        compiler.compile(
            DSL(
                metrics=["sales_amount"],
                filters=[DSLFilter(field="foo", op="DROP", value=1)],
                time=DSLTime(preset="yesterday"),
            ),
            ctx_trade,
        )
    assert ei.value.code == "E_DSL_SCHEMA"


# ============= 权限注入 =============

def test_rls_org_injection(compiler):
    ctx = CompileContext(tenant_id=1, user_id=1, business_line="TRADE",
                         visible_org_ids=[10, 20])
    dsl = DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"))
    r = compiler.compile(dsl, ctx)
    assert "org_id IN" in r.sql


# ============= LIMIT 安全 =============

def test_limit_cap(compiler, ctx_trade):
    with pytest.raises(Exception):
        DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"), limit=1000000)


# ============= 业务 Token 乘数 =============

def test_sensitive_metric_multiplier(compiler, ctx_trade):
    dsl_normal = DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"))
    dsl_hi = DSL(metrics=["net_profit"], time=DSLTime(preset="last_month", grain="month"))
    r1 = compiler.compile(dsl_normal, ctx_trade)
    r2 = compiler.compile(dsl_hi, ctx_trade)
    assert r2.biz_token_estimate > r1.biz_token_estimate


# ============= 角色化指标包 & 权限 =============

def test_metric_in_pack_passes(compiler, ctx_trade):
    """用户角色包内的指标可以查."""
    ctx_trade.allowed_metrics = ["sales_amount", "sales_tonnage"]
    ctx_trade.primary_role = "SALES_REP"
    dsl = DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"))
    r = compiler.compile(dsl, ctx_trade)
    assert r.sql


def test_metric_out_of_pack_rejected(compiler, ctx_trade):
    """不在角色包内的指标拒绝."""
    ctx_trade.allowed_metrics = ["sales_amount"]    # 业务员只能看销售额
    ctx_trade.primary_role = "SALES_REP"
    dsl = DSL(metrics=["customer_irr"], time=DSLTime(preset="last_month"))
    with pytest.raises(CompileError) as ei:
        compiler.compile(dsl, ctx_trade)
    assert ei.value.code == "E_METRIC_OUT_OF_PACK"


def test_all_metrics_pack(compiler, ctx_trade):
    """老板 __ALL__ 表示全部可见."""
    ctx_trade.allowed_metrics = ["__ALL__"]
    ctx_trade.primary_role = "OWNER"
    dsl = DSL(metrics=["net_profit", "customer_irr"], time=DSLTime(preset="last_month", grain="month"))
    r = compiler.compile(dsl, ctx_trade)
    assert r.sql


def test_auth_required_passes_with_scope(compiler, ctx_trade):
    """有 finance.profit.read scope 可以查 net_profit."""
    ctx_trade.allowed_metrics = ["__ALL__"]
    ctx_trade.scopes = ["sales.read", "finance.profit.read"]
    dsl = DSL(metrics=["net_profit"], time=DSLTime(preset="last_month", grain="month"))
    r = compiler.compile(dsl, ctx_trade)
    assert r.sql


def test_empty_allowed_metrics_means_unrestricted(compiler, ctx_trade):
    """allowed_metrics=None (老调用兼容) 不限制."""
    ctx_trade.allowed_metrics = None
    dsl = DSL(metrics=["sales_amount"], time=DSLTime(preset="yesterday"))
    r = compiler.compile(dsl, ctx_trade)
    assert r.sql
