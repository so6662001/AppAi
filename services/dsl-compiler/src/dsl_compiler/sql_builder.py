"""SQL 片段构造工具。

故意保持简洁: 只生成 StarRocks 兼容的 ANSI SQL, 不做花哨重写。
DSL 编译器通过它把 metrics + dims + filters + time 组合成 SQL。
"""
from __future__ import annotations
from datetime import date
from typing import Any
import re

from .models import MetricDef, DSL, CompileContext


# ----------------------------- 字段 / 维度解析 -----------------------------

def parse_field(field: str) -> tuple[str, str]:
    """'org.region' → ('org', 'region')。"""
    if "." in field:
        a, b = field.split(".", 1)
        return a.strip(), b.strip()
    return "", field.strip()


def safe_identifier(name: str) -> str:
    """避免 SQL 注入: 只允许字母数字下划线。"""
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise ValueError(f"非法标识符: {name}")
    return name


# ----------------------------- 参数化 -----------------------------

class ParamBag:
    """收集查询参数, 输出 :name 风格 SQL + dict。"""
    def __init__(self):
        self._counter = 0
        self.values: dict[str, Any] = {}

    def add(self, v: Any) -> str:
        self._counter += 1
        key = f"p{self._counter}"
        self.values[key] = v
        return f":{key}"

    def add_list(self, vs: list) -> str:
        return "(" + ",".join(self.add(v) for v in vs) + ")"


# ----------------------------- 过滤条件 -----------------------------

def build_where(filters: list, params: ParamBag,
                from_d: date, to_d: date,
                time_field: str = "biz_date",
                tenant_id: int = 0,
                rls_org_ids: list[int] | None = None,
                rls_warehouse_ids: list[int] | None = None) -> str:
    parts: list[str] = []

    parts.append(f"tenant_id = {params.add(tenant_id)}")
    parts.append(f"{safe_identifier(time_field)} BETWEEN {params.add(from_d)} AND {params.add(to_d)}")

    if rls_org_ids:
        parts.append(f"org_id IN {params.add_list(rls_org_ids)}")
    if rls_warehouse_ids:
        parts.append(f"warehouse_id IN {params.add_list(rls_warehouse_ids)}")

    for f in filters or []:
        _, col = parse_field(f.field)
        col = safe_identifier(col)
        op = f.op
        if op == "is_null":
            parts.append(f"{col} IS NULL")
        elif op == "not_null":
            parts.append(f"{col} IS NOT NULL")
        elif op in ("in", "not_in"):
            sql_op = "IN" if op == "in" else "NOT IN"
            parts.append(f"{col} {sql_op} {params.add_list(list(f.value))}")
        elif op == "between":
            parts.append(f"{col} BETWEEN {params.add(f.value[0])} AND {params.add(f.value[1])}")
        elif op == "like":
            parts.append(f"{col} LIKE {params.add(f.value)}")
        else:
            parts.append(f"{col} {op} {params.add(f.value)}")

    if f_extra := None:
        parts.append(f_extra)
    return " AND ".join(parts)


# ----------------------------- SELECT 列 -----------------------------

def metric_select_expr(m: MetricDef, grain: str) -> str:
    """单指标 SELECT 表达式 + 别名。"""
    formula = m.formula or ""
    # snapshot + 跨日: AVG of daily SUM (内层先按 snap_date 聚合)
    if m.semantics == "snapshot" and (grain or "day").lower() != "day":
        agg = (m.time_agg or "avg").lower()
        if agg == "avg":
            # 假设 formula 形如 SUM(xxx), 转成 AVG_OF_DAILY 占位; 真实编译时由 CTE 包一层
            return f"{formula} AS {safe_identifier(m.name)}"
        if agg == "first":
            return f"MIN_BY({formula}, snap_date) AS {safe_identifier(m.name)}"
        if agg == "last":
            return f"MAX_BY({formula}, snap_date) AS {safe_identifier(m.name)}"
    return f"{formula} AS {safe_identifier(m.name)}"


def dim_select_expr(field: str, time_grain: str = "day") -> tuple[str, str]:
    """返回 (SELECT 表达式, group_by 表达式)。"""
    tab, col = parse_field(field)
    if tab == "date" and col == "date_key":
        from .time_resolver import date_trunc_expr
        expr = date_trunc_expr(time_grain, "biz_date")
        return f"{expr} AS biz_date", expr
    col = safe_identifier(col)
    return col, col


def build_order_by(order_by: list, default_metric: str | None) -> str:
    if not order_by:
        return f"ORDER BY {safe_identifier(default_metric)} DESC" if default_metric else ""
    parts = []
    for o in order_by:
        _, col = parse_field(o.field)
        d = "ASC" if (o.dir or "desc").upper() == "ASC" else "DESC"
        parts.append(f"{safe_identifier(col)} {d}")
    return "ORDER BY " + ", ".join(parts)
