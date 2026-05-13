"""把 SQL 执行结果渲染成给前端展示的 blocks (KPI/table/chart) + 一句话总结."""
from __future__ import annotations
from typing import Any


def render(rows: list[dict], dsl: dict, summary_extra: str = "") -> tuple[list[dict], str]:
    blocks: list[dict] = []
    metrics = dsl.get("metrics") or []
    if not rows:
        return blocks, "本次查询无数据。" + (summary_extra or "")

    first = rows[0]

    # ============ KPI: 仅 1 行 / 0 维度 ============
    if len(rows) == 1 and not dsl.get("dimensions"):
        kpis = []
        for m in metrics:
            v = first.get(m)
            if v is None: continue
            kpis.append({"metric": m, "label": m, "value": v, "unit": "", "format": _fmt(m)})
        if kpis:
            blocks.append({"type": "kpi", "kpis": kpis})

    # ============ 表格: 多行 ============
    if len(rows) > 1 or dsl.get("dimensions"):
        cols = list(first.keys())
        blocks.append({
            "type": "table",
            "columns": cols,
            "rows": rows[:100],
        })

    # ============ 图表建议 ============
    chart = _suggest_chart(rows, dsl)
    if chart:
        blocks.append(chart)

    # ============ 总结 ============
    summary = _summarize(rows, dsl) + ((" " + summary_extra) if summary_extra else "")
    return blocks, summary


def _fmt(metric_name: str) -> str:
    if "rate" in metric_name or "ratio" in metric_name or "margin" in metric_name:
        return "percent"
    if "ton" in metric_name:
        return "ton"
    if "price" in metric_name:
        return "price"
    if "days" in metric_name:
        return "days"
    return "amount"


def _suggest_chart(rows: list[dict], dsl: dict) -> dict | None:
    metrics = dsl.get("metrics") or []
    dims = dsl.get("dimensions") or []
    grain = dsl.get("time", {}).get("grain", "day")

    # 时间维 + 1 个指标 → 折线
    if "date.date_key" in dims or grain in ("day", "week", "month"):
        if "biz_date" in (rows[0] if rows else {}):
            return {
                "type": "chart", "chart": "line",
                "x": "biz_date",
                "series": [{"name": m, "field": m} for m in metrics[:2]],
                "rows": rows[:200],
            }

    # 分类维度 + 1 个指标 → 柱状
    if dims and metrics:
        first_dim = dims[0].split(".")[-1]
        if first_dim in (rows[0] if rows else {}):
            return {
                "type": "chart", "chart": "bar",
                "x": first_dim,
                "series": [{"name": metrics[0], "field": metrics[0]}],
                "rows": rows[:50],
            }

    return None


def _summarize(rows: list[dict], dsl: dict) -> str:
    """超简化的"一句话总结"。生产应该调小模型生成更自然的中文。"""
    metrics = dsl.get("metrics") or []
    time = dsl.get("time", {})
    period = time.get("preset", "")

    if len(rows) == 1 and not dsl.get("dimensions"):
        parts = []
        for m in metrics:
            v = rows[0].get(m)
            if v is None: continue
            parts.append(f"{m} = {_human(v)}")
        return f"{period} " + ", ".join(parts)

    if rows:
        m1 = metrics[0] if metrics else None
        top = rows[0]
        if m1 and m1 in top:
            return f"{period} 查询返回 {len(rows)} 条记录, Top1: {_pick_dim_value(top)} {m1}={_human(top[m1])}"
    return f"{period} 查询返回 {len(rows)} 条记录"


def _human(v: Any) -> str:
    try:
        f = float(v)
    except Exception:
        return str(v)
    if abs(f) >= 1e8: return f"{f/1e8:.2f} 亿"
    if abs(f) >= 1e4: return f"{f/1e4:.1f} 万"
    return f"{f:.2f}".rstrip("0").rstrip(".")


def _pick_dim_value(row: dict) -> str:
    for k, v in row.items():
        if isinstance(v, str): return v
    return str(next(iter(row.values()), ""))
