"""FastAPI 入口."""
from __future__ import annotations
import logging
import os
from fastapi import FastAPI

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from . import engine


logging.basicConfig(level="INFO",
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("advice.app")


app = FastAPI(title="Advice Engine", version="0.1.0")
_scheduler = BackgroundScheduler()

SCAN_INTERVAL = int(os.environ.get("SCAN_INTERVAL", 3600))


@app.on_event("startup")
def on_start():
    _scheduler.add_job(engine.scan_once,
        IntervalTrigger(seconds=SCAN_INTERVAL),
        id="scan", max_instances=1, coalesce=True, replace_existing=True)
    _scheduler.start()
    log.info("started, scan_interval=%ss", SCAN_INTERVAL)


@app.on_event("shutdown")
def on_stop():
    _scheduler.shutdown(wait=False)


@app.get("/health")
def health():
    return {"status": "ok", "rules_loaded": len(engine.load_rules())}


@app.post("/internal/scan-now")
def scan_now():
    n = engine.scan_once()
    return {"hits": n}


@app.get("/internal/rules")
def list_rules():
    return [{"id": r.id, "title": r.title, "severity": r.severity, "when": r.when}
            for r in engine.load_rules()]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8600)))
