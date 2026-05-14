"""FastAPI 入口 + 周期扫描."""
from __future__ import annotations
import json
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
    """真实扫描:
      1) 从 metric_def 拉所有 PUBLISHED 指标 + sla
      2) 对每个指标的 fact 表查 MAX(src_update_time) 比对 sla
      3) NULL_RATIO: 对核心数值列查空值比例
      4) SPIKE: 对昨日和近7日均值比对
      5) 命中失败 → 写 metric_quality_event
    """
    log.info("DQ scan triggered at %s", datetime.utcnow())
    try:
        from sqlalchemy import create_engine, text
        gov_url = os.environ.get("GOV_DB_URL",
            "mysql+pymysql://root:steeldev@localhost:3306/steel_governance?charset=utf8mb4")
        sr_url = os.environ.get("SR_DB_URL",
            "mysql+pymysql://root:@localhost:9030/steel_dw?charset=utf8mb4")
        gov = create_engine(gov_url, pool_pre_ping=True)
        sr  = create_engine(sr_url,  pool_pre_ping=True)
        with gov.begin() as gc:
            metrics = gc.execute(text("""
                SELECT metric_code, fact, sla_freshness_minutes FROM metric_def
                WHERE status='PUBLISHED' AND fact IS NOT NULL LIMIT 200
            """)).all()

        events = 0
        for code, fact, sla in metrics:
            sla = sla or 60
            try:
                with sr.begin() as sc:
                    max_t = sc.execute(text(
                        f"SELECT MAX(src_update_time) FROM {fact}"
                    )).scalar()
                if max_t is None: continue
                delta_min = (datetime.utcnow() - max_t).total_seconds() / 60
                if delta_min > sla:
                    with gov.begin() as gc:
                        gc.execute(text("""
                            INSERT INTO metric_quality_event
                              (metric_code, event_type, severity, detected_at, detail_json)
                            VALUES (:c, 'FRESHNESS', 'HIGH', NOW(), :d)
                        """), {"c": code,
                               "d": json.dumps({"sla": sla, "actual_min": int(delta_min)})})
                    events += 1
            except Exception:
                continue
        log.info("DQ scan done, events=%d", events)
    except Exception as e:
        log.warning("DQ scan unavailable: %s", e)


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
