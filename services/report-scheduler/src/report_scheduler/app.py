"""FastAPI 入口

提供:
  - 健康检查
  - 手动触发某 report 立即执行 (调试用)
  - 列出/获取 due 报表

注意: 报表的 CRUD 走主 Java/registry 后端, 此服务只负责"调度执行+推送"。
"""
from __future__ import annotations
import logging
import os
from datetime import datetime

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from .config import settings
from .db import get_engine
from .scheduler import start as start_scheduler, stop as stop_scheduler, run_one_now
from .cron import next_run_at


logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
log = logging.getLogger("scheduler.app")


app = FastAPI(title="Report Scheduler", version="0.1.0")


@app.on_event("startup")
def on_startup():
    start_scheduler()
    log.info("API listening on %s:%s", settings.api_host, settings.api_port)


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/health")
def health():
    return {"status": "ok", "tz": settings.tz, "scan_interval": settings.scan_interval_seconds}


@app.post("/internal/run-now/{report_id}")
def run_now(report_id: int):
    sql = text("""SELECT * FROM scheduled_report WHERE report_id=:rid AND status<>'DELETED'""")
    with get_engine().begin() as conn:
        row = conn.execute(sql, {"rid": report_id}).mappings().first()
    if not row:
        raise HTTPException(404, "report not found")
    import json
    report = dict(row)
    for k in ("dsl_json", "render_blocks", "chart_spec", "recipients", "channels"):
        v = report.get(k)
        if isinstance(v, str):
            try: report[k] = json.loads(v)
            except Exception: pass
    run_one_now(report)
    return {"status": "submitted", "report_id": report_id}


@app.get("/internal/next-run-preview")
def preview_cron(cron_expr: str | None = None,
                 schedule_type: str = "cron",
                 tz: str | None = None):
    """工具接口: 验证 cron 解析。"""
    try:
        nxt = next_run_at(cron_expr, schedule_type, datetime.utcnow(), tz or settings.tz)
        return {"next_run_at": nxt.isoformat() if nxt else None}
    except Exception as e:
        raise HTTPException(400, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
