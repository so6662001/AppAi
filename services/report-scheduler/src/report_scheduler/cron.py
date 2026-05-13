"""Cron 解析 - 计算下次执行时间。

支持:
- 6 段标准 cron: '0 0 8 * * ?'  (秒 分 时 日 月 周)
- 简化指令: schedule_type=daily/weekly/monthly + cron_expr 留空
"""
from __future__ import annotations
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from croniter import croniter


def next_run_at(cron_expr: str | None, schedule_type: str,
                base: datetime, tz: str = "Asia/Shanghai") -> datetime | None:
    if schedule_type == "once":
        return None  # 只跑一次的报表执行完就 EXPIRED

    tzinfo = ZoneInfo(tz)
    base = base.astimezone(tzinfo) if base.tzinfo else base.replace(tzinfo=tzinfo)

    # 简化指令 fallback
    expr = cron_expr
    if not expr:
        if schedule_type == "daily":
            expr = "0 0 8 * * *"        # 每天 8:00
        elif schedule_type == "weekly":
            expr = "0 0 8 * * 1"        # 周一 8:00
        elif schedule_type == "monthly":
            expr = "0 0 8 1 * *"        # 每月 1 号 8:00
        else:
            return None

    # croniter 不支持 6 段含秒, 需要适配
    parts = expr.split()
    if len(parts) == 6:
        # 把 6 段去掉秒, 同时把 ? 替换为 *
        _, m, h, dom, mo, dow = parts
        expr5 = f"{m} {h} {dom} {mo} {dow}".replace("?", "*")
    else:
        expr5 = expr.replace("?", "*")

    it = croniter(expr5, base)
    return it.get_next(datetime)
