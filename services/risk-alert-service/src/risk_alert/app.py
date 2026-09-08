"""FastAPI 入口 - 健康检查 + 手动触发扫描."""
from __future__ import annotations
import logging
from fastapi import FastAPI

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .config import settings
from .engine import scan_once
from .rules import load_rules


logging.basicConfig(level="INFO",
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("risk.app")


app = FastAPI(title="Risk Alert Service", version="0.1.0")
_scheduler = BackgroundScheduler(timezone=settings.tz)


@app.on_event("startup")
def on_start():
    _scheduler.add_job(
        scan_once,
        trigger=IntervalTrigger(seconds=settings.scan_interval_sec),
        id="risk_scan", max_instances=1, coalesce=True, replace_existing=True,
    )
    _scheduler.start()
    log.info("started, scan interval=%ss", settings.scan_interval_sec)


@app.on_event("shutdown")
def on_stop():
    _scheduler.shutdown(wait=False)


@app.get("/health")
def health():
    rules = load_rules(settings.metrics_dir)
    return {"status": "ok", "rules_loaded": len(rules), "tz": settings.tz,
            "scan_interval_sec": settings.scan_interval_sec}


@app.post("/internal/scan-now")
def scan_now():
    hits = scan_once()
    return {"status": "ok", "hits": hits}


@app.get("/internal/rules")
def list_rules():
    rules = load_rules(settings.metrics_dir)
    return [{
        "id": r.id, "metric": r.metric, "when": r.when, "severity": r.severity,
        "cooldown_hours": r.cooldown_hours,
    } for r in rules]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
