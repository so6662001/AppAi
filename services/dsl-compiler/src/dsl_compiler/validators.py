"""DSL 校验 + 权限 + 业务类型裁剪。"""
from __future__ import annotations
from typing import Iterable

from .models import DSL, MetricDef, CompileContext, CompileError
from .registry import MetricRegistry


# 允许的过滤操作符
_OP_WHITELIST = {"=", "!=", ">", ">=", "<", "<=",
                 "in", "not_in", "between", "like", "is_null", "not_null"}


def validate_dsl_basic(dsl: DSL) -> None:
    if not dsl.metrics:
        raise CompileError("E_DSL_SCHEMA", "metrics 不能为空")
    if dsl.limit > 50000:
        raise CompileError("E_DSL_SCHEMA", "limit 不能超过 50000")
    for f in dsl.filters:
        if f.op not in _OP_WHITELIST:
            raise CompileError("E_DSL_SCHEMA", f"非法操作符: {f.op}")
        if f.op in ("in", "not_in") and not isinstance(f.value, (list, tuple)):
            raise CompileError("E_DSL_SCHEMA", f"{f.op} 的 value 必须是数组")
        if f.op == "between":
            if not (isinstance(f.value, (list, tuple)) and len(f.value) == 2):
                raise CompileError("E_DSL_SCHEMA", "between 的 value 必须是 [from, to]")


def resolve_metrics(dsl: DSL, registry: MetricRegistry,
                    ctx: CompileContext) -> list[MetricDef]:
    """根据指标名/编号/同义词找出 MetricDef, 并做业务类型/权限校验。"""
    resolved: list[MetricDef] = []
    for key in dsl.metrics:
        m = registry.get(key)
        if not m:
            raise CompileError(
                "E_METRIC_NOT_FOUND",
                f"指标不存在或不在同义词表: {key}",
                hint="请通过同义词扩展或新增指标"
            )
        if m.status not in ("PUBLISHED", "APPROVED"):
            raise CompileError(
                "E_METRIC_STATUS",
                f"指标 {m.name} 当前状态 {m.status}, 不可用"
            )
        if ctx.business_line and m.applicable and ctx.business_line not in m.applicable:
            raise CompileError(
                "E_NOT_APPLICABLE",
                f"指标 {m.label or m.name} 不适用于当前业务类型 {ctx.business_line}",
                hint=f"该指标适用于: {','.join(m.applicable)}"
            )
        if m.auth_required:
            missing = [s for s in m.auth_required if s not in ctx.scopes]
            if missing:
                raise CompileError(
                    "E_PERMISSION",
                    f"指标 {m.name} 需要权限 {missing}",
                    hint="请联系管理员申请"
                )
        resolved.append(m)
    return resolved


def expand_dependencies(metrics: list[MetricDef],
                        registry: MetricRegistry,
                        depth: int = 0) -> list[MetricDef]:
    """递归展开 requires_metrics, 最多 3 层。"""
    if depth > 3:
        raise CompileError("E_DEP_TOO_DEEP", "指标依赖嵌套超过 3 层", hint="检查循环依赖")
    out: list[MetricDef] = []
    seen: set[str] = set()
    stack: list[tuple[MetricDef, int]] = [(m, 0) for m in metrics]
    while stack:
        m, d = stack.pop()
        if m.name in seen:
            continue
        if d > 3:
            raise CompileError("E_DEP_TOO_DEEP", f"指标 {m.name} 依赖过深")
        seen.add(m.name)
        out.append(m)
        for req in m.requires_metrics or []:
            sub = registry.get(req)
            if not sub:
                raise CompileError("E_METRIC_NOT_FOUND", f"依赖指标缺失: {req}")
            stack.append((sub, d + 1))
    return out


def check_snapshot_semantics(metric: MetricDef, grain: str) -> None:
    """半累积语义检查: snapshot 跨日不能 SUM。"""
    if metric.semantics != "snapshot":
        return
    if (grain or "day").lower() != "day" and (metric.time_agg or "").lower() == "sum":
        raise CompileError(
            "E_SEMI_ADDITIVE",
            f"指标 {metric.label or metric.name} 为时点快照, 跨日不能 SUM",
            hint="建议查看日均值或期末值, 或将时间粒度改为 day"
        )
