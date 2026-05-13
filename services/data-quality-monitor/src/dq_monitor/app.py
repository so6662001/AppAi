"""FastAPI 入口 + 周期扫描."""
from __future__ import annotations
import logging
import os
from datetime import datetime
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import checks


logging.basicConfig(level="INFO")
log = logging.getLogger("dq")


app = FastAPI(title="Data Quality Monitor", version="0.1.0")
_scheduler = BackgroundScheduler()


def _scan():
    # 真实环境: 从 metric_def 拉每个指标的 fact 表 + sla, 跑 4 类检查, 写 metric_quality_event
    log.info("DQ scan triggered at %s", datetime.utcnow())


@app.on_event("startup")
def on_start():
    _scheduler.add_job(_scan, IntervalTrigger(minutes=30), id="dq_scan",
                        max_instances=1, coalesce=True)
    _scheduler.start()


@app.on_event("shutdown")
def on_stop(): _scheduler.shutdown(wait=False)


@app.get("/health")
def health(): return {"status": "ok"}


@app.post("/internal/scan-now")
def scan_now():
    _scan()
    return {"status": "OK"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8900)))
