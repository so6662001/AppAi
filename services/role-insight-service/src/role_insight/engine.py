"""画像引擎核心 - 无副作用纯函数, 易测.

核心算法:
  health_score = Σ kpi_i.weight × score_i × 100
    其中 score_i = clamp01( compare_to_benchmark_or_peer )

  findings = filter rules where when_expr(ctx) is True
"""
from __future__ import annotations
import re
import math
from datetime import date
from typing import Optional

from .models import (
    InsightContext, InsightSnapshot, Finding, ActionItem,
    KpiDef, RuleDef, RoleProfileDef,
)


# ============================================================
# 1) KPI 单项评分: 把指标值映射到 0-1
# ============================================================

def _score_kpi(value: Optional[float], kpi: KpiDef,
               benchmark: Optional[dict] = None,
               peer_avg: Optional[float] = None) -> float:
    """给一个 KPI 评分 (0-1).

    优先级: 行业基准 (p25/p50/p75/top10) > 同组员均值 > 仅按方向给中性 0.5
    direction = HIGHER: 越高越好
    direction = LOWER:  越低越好
    direction = NEUTRAL: 不评分, 返回 0.7
    """
    if value is None:
        return 0.5
    if kpi.direction == "NEUTRAL":
        return 0.7

    # --- 基准评分 (按分位段) ---
    if benchmark and kpi.benchmark:
        p25 = benchmark.get("p25"); p50 = benchmark.get("p50")
        p75 = benchmark.get("p75"); top = benchmark.get("top10")
        if all(v is not None for v in (p25, p50, p75)):
            if kpi.direction == "LOWER":
                # 反过来插值
                if value <= top:    return 1.0
                if value <= p75:    return 0.85
                if value <= p50:    return 0.65
                if value <= p25:    return 0.40
                return 0.20
            else:  # HIGHER
                if value >= top:    return 1.0
                if value >= p75:    return 0.85
                if value >= p50:    return 0.65
                if value >= p25:    return 0.40
                return 0.20

    # --- 同组员对比 ---
    if peer_avg and peer_avg > 0 and kpi.peer_compare:
        ratio = value / peer_avg if peer_avg else 1.0
        if kpi.direction == "LOWER":
            ratio = 1 / ratio if ratio > 0 else 0
        # 1.0 同组 → 0.6, 1.5 倍 → 0.95, 0.5 倍 → 0.25
        return max(0.0, min(1.0, 0.6 + (ratio - 1.0) * 0.7))

    # --- 兜底: 中性 0.6 (有数据但无基准) ---
    return 0.6


# ============================================================
# 2) 健康度评分: 加权聚合 + 分档
# ============================================================

def calc_health_score(ctx: InsightContext) -> tuple[int, str, dict, list]:
    """返回 (总分 0-100, 等级 A-E, 分项明细, 雷达数据)."""
    total = 0.0
    weight_sum = 0.0
    breakdown: dict[str, dict] = {}
    radar: list[dict] = []

    # 按 focus_areas 分类聚合
    area_aggr: dict[str, list] = {a: [] for a in ctx.profile.focus_areas}
    for kpi in ctx.profile.primary_kpis:
        v = ctx.kpi_values.get(kpi.code)
        bm = ctx.benchmarks.get(kpi.code) if kpi.benchmark else None
        peer = ctx.peer_avgs.get(kpi.code) if kpi.peer_compare else None
        s = _score_kpi(v, kpi, bm, peer)
        total += s * kpi.weight
        weight_sum += kpi.weight

        # 雷达数据
        radar.append({
            "code": kpi.code, "label": kpi.label,
            "value": v, "score": round(s * 100),
            "benchmark": bm.get("p50") if bm else None,
            "peer_avg": peer,
            "direction": kpi.direction,
        })

        # 归到对应的 focus_area
        for a in ctx.profile.focus_areas:
            if a.lower() in kpi.code.lower() or a.lower() in kpi.label.lower():
                area_aggr[a].append((kpi, s))
                break
        else:
            # 找不到对应 focus 时归到第一个 area (保证有归宿)
            if ctx.profile.focus_areas:
                area_aggr[ctx.profile.focus_areas[0]].append((kpi, s))

    score = int(round((total / weight_sum * 100) if weight_sum > 0 else 0))
    level = _grade(score)

    for area, items in area_aggr.items():
        if not items:
            breakdown[area] = {"score": 0, "contrib": 0, "kpis": []}
            continue
        avg_s = sum(s for _, s in items) / len(items)
        contrib = sum(s * kpi.weight for kpi, s in items)
        breakdown[area] = {
            "score": int(round(avg_s * 100)),
            "contrib": round(contrib * 100, 1),
            "kpis": [{"code": kpi.code, "label": kpi.label, "score": int(round(s * 100))}
                     for kpi, s in items]
        }

    return score, level, breakdown, radar


def _grade(score: int) -> str:
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    if score >= 40: return "D"
    return "E"


# ============================================================
# 3) 规则求值: 安全的表达式求值
# ============================================================

# 允许引用的辅助函数: benchmark(line, code).field
_BENCHMARK_PATTERN = re.compile(r"benchmark\('([^']+)','([^']+)'\)\.(p25|p50|p75|top10)")


def _eval_when(expr: str, ctx: InsightContext) -> tuple[bool, dict]:
    """安全求值规则 when 表达式.

    可用变量:
      - ctx.kpi_values 里的所有 key
      - 替换 benchmark('TRADE','xxx').p50 = 实际数值
      - 数学比较 / AND OR NOT
    返回 (是否触发, 用到的变量值)
    """
    if not expr:
        return False, {}
    # 先做 benchmark() 替换
    def _bm(m):
        line, code, field = m.group(1), m.group(2), m.group(3)
        bm = ctx.benchmarks.get(code, {})
        v = bm.get(field)
        if v is None:
            return "0"
        return str(v)
    e = _BENCHMARK_PATTERN.sub(_bm, expr)

    # 替换 kpi 变量
    used: dict = {}
    # 按 key 长度倒序替换避免子串问题
    for k in sorted(list(ctx.kpi_values.keys()) + list(ctx.extras.keys()) + list(ctx.peer_avgs.keys()),
                    key=lambda x: -len(x)):
        if k in e:
            if k in ctx.kpi_values:
                v = ctx.kpi_values.get(k, 0) or 0
            elif k in ctx.peer_avgs:
                v = ctx.peer_avgs.get(k, 0) or 0
            else:
                v = ctx.extras.get(k, 0) or 0
            used[k] = v
            e = re.sub(r'\b' + re.escape(k) + r'\b', str(v), e)

    # AND/OR/NOT/= 替换
    e2 = (e.replace(" AND ", " and ")
            .replace(" OR ", " or ")
            .replace(" NOT ", " not ")
            .replace("=", "==")
            .replace(">==", ">=")
            .replace("<==", "<=")
            .replace("!==", "!="))

    # 白名单字符
    allowed = set("0123456789.+-*/()<>!= andortnoTRUEFALSE ")
    if not all(c in allowed or c.isspace() for c in e2):
        return False, used

    try:
        result = bool(eval(e2, {"__builtins__": {}}, {}))  # nosec B307
        return result, used
    except Exception:
        return False, used


# ============================================================
# 4) finding/impact 模板渲染
# ============================================================

def _safe_format(tpl: str, vars: dict) -> str:
    if not tpl:
        return ""
    try:
        return tpl.format(**vars)
    except Exception:
        # 缺少变量时返回原模板, 不抛出
        return tpl


# ============================================================
# 5) 主流程
# ============================================================

def diagnose(ctx: InsightContext) -> InsightSnapshot:
    """跑一次完整画像 - 输入 ctx, 输出 snapshot."""

    # 1) 健康度
    score, level, breakdown, radar = calc_health_score(ctx)

    # 2) 跑规则
    findings: list[Finding] = []
    score_penalty = 0
    for rule in ctx.profile.rules:
        triggered, used = _eval_when(rule.when, ctx)
        if not triggered:
            continue
        # 合并 ctx (kpi + benchmarks p50 + peer_avgs + extras + used)
        vars_dict: dict = {}
        vars_dict.update(ctx.kpi_values)
        vars_dict.update(ctx.peer_avgs)
        vars_dict.update(ctx.extras)
        # 简化的 benchmark 引用: 取 p50 作为 fallback
        for code, bm in ctx.benchmarks.items():
            for fld in ("p25", "p50", "p75", "top10"):
                if bm.get(fld) is not None:
                    vars_dict[f"{code}_{fld}"] = bm[fld]
            # 用 "p50" 作为该规则上下文里 metric 的同名变量
            if "p50" not in vars_dict and bm.get("p50") is not None:
                vars_dict["p50"] = bm["p50"]

        finding = Finding(
            rule_id=rule.id,
            title=rule.title,
            category=rule.category,
            severity=rule.severity,
            finding_text=_safe_format(rule.finding, vars_dict),
            impact_text=_safe_format(rule.impact, vars_dict),
            score_impact=rule.score_impact,
            actions=rule.actions,
            context_values=used,
        )
        findings.append(finding)
        # 负面规则扣分, 正面规则加分 (score_impact 为负则加)
        score_penalty += rule.score_impact

    # 扣分后修正 (上限 -40, 防止单角色被扣穿)
    final_score = max(0, min(100, score - min(40, score_penalty)))

    # 3) 严重度计数
    high = sum(1 for f in findings if f.severity == "HIGH")
    medium = sum(1 for f in findings if f.severity == "MEDIUM")
    low = sum(1 for f in findings if f.severity == "LOW")

    # 4) Top 3 action 建议: 优先 HIGH severity → score_impact 高 → action 数 > 0
    sorted_findings = sorted(
        [f for f in findings if f.actions],
        key=lambda f: (
            {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(f.severity, 3),
            -f.score_impact,
        )
    )
    top_actions = []
    for f in sorted_findings[:3]:
        a = f.actions[0]
        top_actions.append({
            "source_rule": f.rule_id,
            "source_title": f.title,
            "severity": f.severity,
            "label": a.label,
            "type": a.type,
            "path": a.path,
            "prompt": a.prompt,
            "handler": a.handler,
        })

    return InsightSnapshot(
        tenant_id=ctx.tenant_id,
        user_id=ctx.user_id,
        role_code=ctx.role_code,
        role_name=ctx.profile.role_name,
        snap_date=date.today().isoformat(),
        period_month=ctx.period_month,
        health_score=final_score,
        health_level=_grade(final_score),
        score_breakdown=breakdown,
        kpi_radar=radar,
        findings=findings,
        finding_count=len(findings),
        high_count=high,
        medium_count=medium,
        low_count=low,
        top_actions=top_actions,
        explain_trace=[
            f"基础得分(KPI 加权) = {score}",
            f"规则触发 {len(findings)} 条 (HIGH={high}, MED={medium}, LOW={low})",
            f"扣分 = min(40, Σ score_impact) = {min(40, score_penalty)}",
            f"最终得分 = {final_score} ({_grade(final_score)})",
        ],
    )
