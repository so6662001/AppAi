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


import re
_TABLE_WHITELIST_RE = re.compile(r"^(dim|dwd|dws|ads|fact)_[a-z0-9_]{2,64}$")


def _is_valid_fact_table(fact: str) -> bool:
    """白名单: 必须是 dim_/dwd_/dws_/ads_/fact_ 开头, 防 SQL 标识符注入."""
    return bool(fact) and bool(_TABLE_WHITELIST_RE.match(fact))


def _scan():
    """周期质量扫描: 检查 metric_def 中每个指标的 fact 新鲜度.

    安全:
      - fact 表名严格白名单 (防止 metric_def 被污染时注入)
      - 时间比较统一 UTC (避免时区错位)
      - 单个指标失败不影响其他
    """
    now_utc = datetime.utcnow()
    log.info("DQ scan triggered at %s UTC", now_utc.isoformat())
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
        skipped = 0
        for code, fact, sla in metrics:
            sla = sla or 60
            if not _is_valid_fact_table(fact):
                log.warning("skip invalid fact name: %s (metric=%s)", fact, code)
                skipped += 1
                continue
            try:
                # fact 已通过白名单校验, 此处 f-string 安全
                with sr.begin() as sc:
                    max_t = sc.execute(text(
                        f"SELECT MAX(src_update_time) FROM {fact}"  # nosec B608
                    )).scalar()
                if max_t is None: continue
                # 统一用 UTC 比较 (假设 DB 列也是 UTC; 真实场景应在 DDL 用 UTC_TIMESTAMP)
                delta_min = (now_utc - max_t).total_seconds() / 60
                if delta_min > sla:
                    with gov.begin() as gc:
                        gc.execute(text("""
                            INSERT INTO metric_quality_event
                              (metric_code, event_type, severity, detected_at, detail_json)
                            VALUES (:c, 'FRESHNESS', 'HIGH', NOW(), :d)
                        """), {"c": code,
                               "d": json.dumps({"sla_minutes": sla,
                                                  "actual_minutes": int(delta_min)})})
                    events += 1
            except Exception as e:
                log.debug("scan metric %s failed: %s", code, e)
                continue
        log.info("DQ scan done, events=%d, skipped=%d", events, skipped)
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
