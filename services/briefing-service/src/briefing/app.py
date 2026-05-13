"""FastAPI 入口 - 8 个 /v1/briefing/* 接口 + 每天 05:00 自动生成."""
from __future__ import annotations
import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, HTTPException

from .config import settings
from . import db, generator


logging.basicConfig(level="INFO",
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("briefing.app")


app = FastAPI(title="Briefing Service", version="0.1.0")
_scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_start():
    try:
        cron_parts = settings.generate_cron.split()
        if len(cron_parts) == 5:
            m, h, d, mo, w = cron_parts
            trigger = CronTrigger(minute=m, hour=h, day=d, month=mo, day_of_week=w)
        else:
            trigger = CronTrigger(hour=5, minute=0)
        _scheduler.add_job(generator.generate_all, trigger, id="generate_daily",
                            max_instances=1, coalesce=True, replace_existing=True)
        _scheduler.start()
        log.info("scheduler started, cron=%s", settings.generate_cron)
    except Exception:
        log.exception("scheduler start failed")


@app.on_event("shutdown")
def on_stop():
    _scheduler.shutdown(wait=False)


def _ctx(request: Request) -> tuple[int, int]:
    return (int(request.headers.get("X-Tenant-Id", "1")),
            int(request.headers.get("X-User-Id", "1")))


@app.get("/health")
def health():
    return {"status": "ok", "cron": settings.generate_cron}


@app.get("/v1/briefing/today")
def get_today(request: Request, date_: str | None = None):
    tid, uid = _ctx(request)
    bd = date.fromisoformat(date_) if date_ else date.today()
    cards = db.list_today(tid, uid, bd)
    if not cards:
        # 即刻生成 (兜底)
        generator.generate_for_user(tid, uid, bd)
        cards = db.list_today(tid, uid, bd)
    return {
        "biz_date": bd.isoformat(),
        "user": {"id": uid},
        "cards": cards,
    }


@app.get("/v1/briefing/history")
def history(request: Request, from_: str = None, to: str = None,
            page: int = 1, size: int = 30):
    tid, uid = _ctx(request)
    today = date.today()
    f = date.fromisoformat(from_) if from_ else today - timedelta(days=30)
    t = date.fromisoformat(to) if to else today
    total, items = db.list_history(tid, uid, f, t, page, size)
    return {"total": total, "items": items}


@app.post("/v1/briefing/cards/{card_id}/mark-read")
def card_read(card_id: int):
    db.mark_read(card_id)
    return {"status": "OK"}


@app.post("/v1/briefing/cards/{card_id}/act")
def card_act(card_id: int):
    db.mark_acted(card_id)
    return {"status": "OK"}


@app.post("/v1/briefing/cards/{card_id}/ignore")
def card_ignore(card_id: int):
    db.mark_ignored(card_id)
    return {"status": "OK"}


@app.post("/v1/briefing/cards/{card_id}/feedback")
def card_feedback(card_id: int, request: Request, body: dict):
    tid, uid = _ctx(request)
    ok = db.save_feedback(card_id, tid, uid,
                          vote=body.get("vote", "UP"),
                          reason=body.get("reason"),
                          remark=body.get("remark"))
    return {"status": "OK" if ok else "FAILED"}


@app.get("/v1/briefing/layout")
def get_layout(request: Request):
    tid, uid = _ctx(request)
    return db.get_layout(tid, uid) or {}


@app.put("/v1/briefing/layout")
def put_layout(request: Request, body: dict):
    tid, uid = _ctx(request)
    db.upsert_layout(tid, uid, body)
    return {"status": "OK"}


# 调试: 手动触发生成
@app.post("/internal/generate-now")
def generate_now():
    n = generator.generate_all()
    return {"generated": n}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
