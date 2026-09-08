"""ETL Runner: 调度 + 手动触发."""
from __future__ import annotations
import logging
import os
from fastapi import FastAPI, HTTPException
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import jobs


logging.basicConfig(level="INFO",
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("etl.app")


app = FastAPI(title="ETL Runner", version="0.1.0")
_scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_start():
    # 每天 00:30 跑库存日快照
    _scheduler.add_job(jobs.inv_daily_snapshot,
        CronTrigger(hour=0, minute=30),
        id="inv_snapshot", max_instances=1, coalesce=True, replace_existing=True)
    _scheduler.start()
    log.info("started")


@app.on_event("shutdown")
def on_stop():
    _scheduler.shutdown(wait=False)


@app.get("/health")
def health(): return {"status": "ok", "jobs": list(jobs.JOBS.keys())}


@app.post("/internal/run/{job}")
def run_job(job: str):
    fn = jobs.JOBS.get(job)
    if not fn: raise HTTPException(404, "unknown job: " + job)
    n = fn()
    return {"job": job, "rows": n}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8700)))
