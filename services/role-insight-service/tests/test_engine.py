"""画像引擎核心测试 - 评分公式 + 规则触发 + 模板渲染."""
from __future__ import annotations
import pytest
from role_insight.models import (
    InsightContext, RoleProfileDef, KpiDef, RuleDef, ActionItem,
)
from role_insight.engine import (
    calc_health_score, diagnose, _eval_when, _score_kpi, _grade,
)


# ----- _score_kpi -----

def test_score_higher_better_top():
    kpi = KpiDef(code="m", weight=1, direction="HIGHER", benchmark=True)
    bm = {"p25":50, "p50":100, "p75":150, "top10":200}
    assert _score_kpi(220, kpi, bm) == 1.0   # >= top10

def test_score_higher_better_low():
    kpi = KpiDef(code="m", weight=1, direction="HIGHER", benchmark=True)
    bm = {"p25":50, "p50":100, "p75":150, "top10":200}
    assert _score_kpi(40, kpi, bm) == 0.20   # < p25

def test_score_lower_better_top():
    kpi = KpiDef(code="ccc", weight=1, direction="LOWER", benchmark=True)
    bm = {"p25":70, "p50":56, "p75":38, "top10":22}
    assert _score_kpi(20, kpi, bm) == 1.0    # 越低越好, 20 <= top10

def test_score_lower_better_mid():
    kpi = KpiDef(code="ccc", weight=1, direction="LOWER", benchmark=True)
    bm = {"p25":70, "p50":56, "p75":38, "top10":22}
    assert _score_kpi(48, kpi, bm) == 0.65   # 38 < 48 <= 56

def test_score_peer_compare_better():
    """同组员对比 - 比同事高 50% → 接近 0.95."""
    kpi = KpiDef(code="m", weight=1, direction="HIGHER", peer_compare=True)
    s = _score_kpi(150, kpi, peer_avg=100)
    assert 0.9 <= s <= 1.0

def test_score_none_value():
    kpi = KpiDef(code="m", weight=1)
    assert _score_kpi(None, kpi) == 0.5


# ----- 等级映射 -----

def test_grade_a(): assert _grade(85) == "A"
def test_grade_b(): assert _grade(72) == "B"
def test_grade_c(): assert _grade(60) == "C"
def test_grade_d(): assert _grade(45) == "D"
def test_grade_e(): assert _grade(20) == "E"


# ----- 规则求值 -----

def _make_ctx(values: dict, extras: dict = None, benchmarks: dict = None) -> InsightContext:
    return InsightContext(
        tenant_id=1, user_id=1, role_code="X", period_month="2026-05",
        profile=RoleProfileDef(role_code="X", role_name="x"),
        kpi_values=values, benchmarks=benchmarks or {},
        peer_avgs={}, extras=extras or {},
    )

def test_when_simple_gt():
    ctx = _make_ctx({"x": 100, "y": 50})
    ok, used = _eval_when("x > 80", ctx)
    assert ok is True
    assert used == {"x": 100}

def test_when_and_or():
    ctx = _make_ctx({"a": 10, "b": 20})
    ok, _ = _eval_when("a > 5 AND b > 15", ctx)
    assert ok is True
    ok, _ = _eval_when("a > 50 OR b > 15", ctx)
    assert ok is True
    ok, _ = _eval_when("a > 50 OR b > 50", ctx)
    assert ok is False

def test_when_benchmark_inline():
    """benchmark('TRADE','xxx').p50 应被替换为实际值."""
    ctx = _make_ctx(
        {"ccc": 60},
        benchmarks={"ccc": {"p25":70,"p50":56,"p75":38,"top10":22}},
    )
    ok, _ = _eval_when("ccc > benchmark('TRADE','ccc').p50", ctx)
    assert ok is True

def test_when_unsafe_blocked():
    """白名单过滤 - 拒绝 import / __import__."""
    ctx = _make_ctx({"x": 1})
    ok, _ = _eval_when("__import__('os')", ctx)
    assert ok is False


# ----- 完整诊断 -----

def _sales_rep_profile():
    return RoleProfileDef(
        role_code="REP", role_name="销售员",
        business_line="TRADE", focus_areas=["sales","customer"],
        primary_kpis=[
            KpiDef(code="my_tgp",  weight=0.5, direction="HIGHER", benchmark=True, label="吨毛利"),
            KpiDef(code="my_cust", weight=0.5, direction="HIGHER", label="活跃客户"),
        ],
        rules=[
            RuleDef(id="LOW_TGP", category="WEAKNESS", severity="HIGH",
                title="吨毛利低",
                when="my_tgp < 180",
                finding="吨毛利 {my_tgp:.0f} 低于团队均值 {peer:.0f}",
                impact="少挣 {potential:.0f}",
                actions=[ActionItem(label="AI 帮我看", type="chat", prompt="为什么我吨毛利低?")],
                score_impact=20),
            RuleDef(id="FEW_CUST", category="OPPORTUNITY", severity="MEDIUM",
                title="客户少",
                when="my_cust < 10",
                finding="客户仅 {my_cust} 个",
                impact="",
                actions=[ActionItem(label="开发新客户", type="navigate", path="/cust")],
                score_impact=8),
        ],
    )


def test_diagnose_low_score():
    p = _sales_rep_profile()
    ctx = InsightContext(
        tenant_id=1, user_id=1, role_code="REP", period_month="2026-05",
        profile=p,
        kpi_values={"my_tgp": 120, "my_cust": 5},
        benchmarks={"my_tgp": {"p25":120,"p50":180,"p75":220,"top10":280,"direction":"HIGHER"}},
        peer_avgs={},
        extras={"peer": 186, "potential": 9000},
    )
    snap = diagnose(ctx)
    assert snap.role_code == "REP"
    assert snap.health_score < 70
    # 两条规则都触发
    assert snap.finding_count == 2
    assert snap.high_count == 1
    assert snap.medium_count == 1
    # finding text 已渲染
    f = next(f for f in snap.findings if f.rule_id == "LOW_TGP")
    assert "120" in f.finding_text
    assert "186" in f.finding_text
    # explain_trace 必有
    assert any("最终得分" in t for t in snap.explain_trace)


def test_diagnose_perfect_score():
    """所有 KPI 在 top10 + 无规则触发 → 高分."""
    p = _sales_rep_profile()
    ctx = InsightContext(
        tenant_id=1, user_id=1, role_code="REP", period_month="2026-05",
        profile=p,
        kpi_values={"my_tgp": 300, "my_cust": 20},
        benchmarks={"my_tgp": {"p25":120,"p50":180,"p75":220,"top10":280,"direction":"HIGHER"}},
        peer_avgs={},
        extras={"peer": 186, "potential": 0},
    )
    snap = diagnose(ctx)
    assert snap.finding_count == 0
    assert snap.health_score >= 70
    assert snap.health_level in ("A", "B")


def test_top_actions_priority_high_first():
    """top_actions 应该 HIGH severity 优先."""
    p = _sales_rep_profile()
    ctx = InsightContext(
        tenant_id=1, user_id=1, role_code="REP", period_month="2026-05",
        profile=p,
        kpi_values={"my_tgp": 100, "my_cust": 3},
        benchmarks={"my_tgp": {"p25":120,"p50":180,"p75":220,"top10":280,"direction":"HIGHER"}},
        peer_avgs={},
        extras={"peer": 186, "potential": 9000},
    )
    snap = diagnose(ctx)
    assert len(snap.top_actions) >= 1
    # 第一条 action 必须是 HIGH (LOW_TGP) 而非 MEDIUM (FEW_CUST)
    assert snap.top_actions[0]["severity"] == "HIGH"


def test_score_breakdown_areas():
    p = _sales_rep_profile()
    ctx = InsightContext(
        tenant_id=1, user_id=1, role_code="REP", period_month="2026-05",
        profile=p,
        kpi_values={"my_tgp": 200, "my_cust": 12},
        benchmarks={"my_tgp": {"p25":120,"p50":180,"p75":220,"top10":280,"direction":"HIGHER"}},
        peer_avgs={}, extras={"peer": 186, "potential": 0},
    )
    snap = diagnose(ctx)
    assert "sales" in snap.score_breakdown or "customer" in snap.score_breakdown
