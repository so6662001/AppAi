"""DSL → SQL 主流水线。

10 个阶段:
  1. Schema 校验
  2. 指标解析 (含同义词)
  3. 客户类型裁剪
  4. 权限注入 (行级/列级)
  5. 派生指标展开
  6. 维度/时间归一
  7. 表与 Join 选择
  8. 比较模式生成
  9. 复杂度评估
 10. SQL 生成 + 加固
"""
from __future__ import annotations
from datetime import date
from typing import Optional

from .models import DSL, MetricDef, CompileContext, CompileResult, CompileError
from .registry import MetricRegistry
from .validators import (
    validate_dsl_basic, resolve_metrics, expand_dependencies, check_snapshot_semantics
)
from .time_resolver import resolve_preset, compare_range, days_in_period, date_trunc_expr
from .sql_builder import (
    ParamBag, build_where, metric_select_expr, dim_select_expr, build_order_by,
    parse_field, safe_identifier,
)


class DSLCompiler:

    def __init__(self, registry: MetricRegistry):
        self.registry = registry

    # ----------------------- 主入口 -----------------------
    def compile(self, dsl: DSL, ctx: CompileContext) -> CompileResult:
        # 1. Schema 校验
        validate_dsl_basic(dsl)

        # 2-3. 指标解析 + 客户类型 + 权限
        metrics = resolve_metrics(dsl, self.registry, ctx)

        # 5. 派生指标展开
        all_metrics = expand_dependencies(metrics, self.registry)

        # 6. 时间归一
        from_d, to_d = self._resolve_time(dsl)
        grain = (dsl.time.grain or "day").lower()

        # 半累积语义校验
        for m in metrics:
            check_snapshot_semantics(m, grain)

        # 7. 表与 Join: 取所有指标的 fact 表, 必须同根
        primary_metric = metrics[0]
        fact = primary_metric.fact or "dws_sales_daily"
        tables_used = sorted({m.fact for m in metrics if m.fact})

        # 8 & 10. SQL 生成
        sql, params, warnings = self._build_sql(dsl, ctx, metrics, fact, grain, from_d, to_d)

        # 9. 复杂度估算 (粗略: 时间跨度 × 估算每日 1000 行)
        est_rows = max(1, days_in_period(from_d, to_d)) * 1000
        if est_rows > 100_000_000:
            raise CompileError(
                "E_COST_EXCEEDED",
                f"预估扫描 {est_rows} 行超过上限",
                hint="请缩小时间范围或增加过滤条件"
            )

        # 计费估算
        biz_token = ctx.bizToken_estimate_base
        for m in metrics:
            biz_token = int(biz_token * (m.bizToken_multiplier or 1.0))

        return CompileResult(
            sql=sql,
            params=params,
            tables_used=tables_used,
            metrics_expanded=[m.name for m in all_metrics],
            est_rows=est_rows,
            warnings=warnings,
            biz_token_estimate=biz_token,
        )

    # ----------------------- 内部辅助 -----------------------

    def _resolve_time(self, dsl: DSL) -> tuple[date, date]:
        if dsl.time.preset:
            return resolve_preset(dsl.time.preset)
        if dsl.time.range:
            r = dsl.time.range
            try:
                from_d = date.fromisoformat(str(r.get("from")))
                to_d = date.fromisoformat(str(r.get("to")))
                return from_d, to_d
            except Exception as e:
                raise CompileError("E_DSL_SCHEMA", f"非法时间范围: {e}")
        raise CompileError("E_DSL_SCHEMA", "必须指定 time.preset 或 time.range")

    def _build_sql(self,
                   dsl: DSL,
                   ctx: CompileContext,
                   metrics: list[MetricDef],
                   fact: str,
                   grain: str,
                   from_d: date,
                   to_d: date) -> tuple[str, dict, list[str]]:
        warnings: list[str] = []
        params = ParamBag()

        # 构造 SELECT 列
        dim_selects: list[str] = []
        group_by: list[str] = []
        for dim in dsl.dimensions:
            s, gb = dim_select_expr(dim, grain)
            dim_selects.append(s)
            group_by.append(gb)

        # 维度 + 默认时间维 (若未显式选)
        if not any(d.startswith("date.") for d in dsl.dimensions):
            if grain != "day":
                tcol = date_trunc_expr(grain, "biz_date")
                dim_selects.insert(0, f"{tcol} AS biz_date")
                group_by.insert(0, tcol)

        metric_selects = [metric_select_expr(m, grain) for m in metrics]

        # 是否需要把 snapshot+AVG 包成内层 CTE
        needs_inner_daily = any(
            m.semantics == "snapshot" and grain != "day"
            and (m.time_agg or "avg").lower() == "avg"
            for m in metrics
        )

        where_clause = build_where(
            filters=dsl.filters,
            params=params,
            from_d=from_d, to_d=to_d,
            time_field="biz_date" if "inv" not in fact else "snap_date",
            tenant_id=ctx.tenant_id,
            rls_org_ids=ctx.visible_org_ids,
            rls_warehouse_ids=ctx.visible_warehouse_ids if "inv" in fact else None,
        )

        # 主查询
        select_cols = ", ".join(dim_selects + metric_selects) if (dim_selects or metric_selects) else "*"
        group_clause = ("GROUP BY " + ", ".join(group_by)) if group_by else ""

        order_by_clause = build_order_by(
            dsl.order_by,
            default_metric=metrics[0].name if metrics else None,
        )

        if needs_inner_daily:
            # 先按 snap_date 聚合, 再跨日 AVG
            inner_dims = ["snap_date"] + group_by
            inner_metrics = [f"{m.formula} AS _{m.name}" for m in metrics if m.semantics == "snapshot"]
            outer_metrics = [f"AVG(_{m.name}) AS {m.name}" if m.semantics == "snapshot"
                             else metric_select_expr(m, grain) for m in metrics]
            sql = f"""\
WITH daily AS (
  SELECT {', '.join(inner_dims + inner_metrics)}
  FROM {safe_identifier(fact)}
  WHERE {where_clause}
  GROUP BY {', '.join(inner_dims)}
)
SELECT {', '.join(dim_selects + outer_metrics)}
FROM daily
{group_clause}
{order_by_clause}
LIMIT {dsl.limit}"""
        else:
            sql = f"""\
SELECT {select_cols}
FROM {safe_identifier(fact)}
WHERE {where_clause}
{group_clause}
{order_by_clause}
LIMIT {dsl.limit}"""

        # 比较模式: 用 UNION ALL 两段并标记 period
        if dsl.compare:
            warnings.append(f"compare mode: {dsl.compare.mode} (使用 base/prev 双查询)")
            prev_from, prev_to = compare_range(from_d, to_d, dsl.compare.mode)
            prev_params = ParamBag()
            # 简化处理: 再编译一段对比时间区间
            prev_where = build_where(
                filters=dsl.filters,
                params=prev_params,
                from_d=prev_from, to_d=prev_to,
                time_field="biz_date" if "inv" not in fact else "snap_date",
                tenant_id=ctx.tenant_id,
                rls_org_ids=ctx.visible_org_ids,
            )
            sql = f"""\
-- 基准期
{sql.strip()}
-- 对比期 ({dsl.compare.mode})
UNION ALL
SELECT {select_cols}, '_PREV' AS _period
FROM {safe_identifier(fact)}
WHERE {prev_where}
{group_clause}
LIMIT {dsl.limit}"""
            params.values.update({f"prev_{k}": v for k, v in prev_params.values.items()})

        return sql.strip(), params.values, warnings
