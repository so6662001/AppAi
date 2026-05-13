"""时间预设(preset) → 具体日期区间。"""
from __future__ import annotations
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


def resolve_preset(preset: str, today: date | None = None) -> tuple[date, date]:
    """返回 (from_date, to_date) 闭区间。"""
    today = today or date.today()
    p = (preset or "").lower()

    if p == "today":
        return today, today
    if p == "yesterday":
        d = today - timedelta(days=1)
        return d, d
    if p == "this_week":
        start = today - timedelta(days=today.weekday())
        return start, today
    if p == "last_week":
        last_monday = today - timedelta(days=today.weekday() + 7)
        last_sunday = last_monday + timedelta(days=6)
        return last_monday, last_sunday
    if p == "mtd":
        return today.replace(day=1), today
    if p == "last_month":
        first_this = today.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return last_month_start, last_month_end
    if p == "qtd":
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        return start, today
    if p == "ytd":
        return today.replace(month=1, day=1), today
    if p == "rolling_7d":
        return today - timedelta(days=6), today
    if p == "rolling_30d":
        return today - timedelta(days=29), today
    if p == "rolling_90d":
        return today - timedelta(days=89), today
    if p == "next_week":
        next_monday = today + timedelta(days=(7 - today.weekday()))
        return next_monday, next_monday + timedelta(days=6)

    raise ValueError(f"unknown preset: {preset}")


def compare_range(from_d: date, to_d: date, mode: str) -> tuple[date, date]:
    """返回与基准期对应的对比期。"""
    days = (to_d - from_d).days + 1
    m = (mode or "").lower()
    if m == "dod":
        return from_d - timedelta(days=1), to_d - timedelta(days=1)
    if m == "wow":
        return from_d - timedelta(days=7), to_d - timedelta(days=7)
    if m == "mom":
        return from_d - relativedelta(months=1), to_d - relativedelta(months=1)
    if m == "yoy":
        return from_d - relativedelta(years=1), to_d - relativedelta(years=1)
    # vs_plan / vs_budget / vs_index 在 SQL 里另行处理
    return from_d, to_d


def days_in_period(from_d: date, to_d: date) -> int:
    return (to_d - from_d).days + 1


def date_trunc_expr(grain: str, col: str = "biz_date") -> str:
    """生成 StarRocks date_trunc 表达式。"""
    g = (grain or "day").lower()
    if g == "day":
        return col
    if g in ("week", "month", "quarter", "year"):
        return f"date_trunc('{g}', {col})"
    return col
