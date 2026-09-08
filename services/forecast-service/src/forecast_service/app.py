"""FastAPI 入口 - 调度 + 手动训练."""
from __future__ import annotations
import logging
from datetime import date, timedelta
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .models import fit_and_forecast


logging.basicConfig(level="INFO",
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("forecast.app")


app = FastAPI(title="Forecast Service", version="0.1.0")
_scheduler = BackgroundScheduler()


def _full_retrain():
    """每周一全量重训: 对每个 scope 拉历史数据 → 训练 → 写 dws_forecast_daily."""
    log.info("full retrain start")
    try:
        # 真实生产: 从 dws_sales_daily 拉每个 material × org 的近 90 天序列
        # 此处给出最小可运行版本: 拉 OVERALL 1 个 scope 跑一遍
        from .runner import train_one_scope, insert_rows
        from datetime import date, timedelta
        history = [(date.today() - timedelta(days=i), 1000 + i * 50)
                    for i in range(60, 0, -1)]
        rows = train_one_scope("OVERALL", "ALL", "SALES_TON", history,
                                horizon=settings.horizon_days,
                                use_prophet=settings.use_prophet, tenant_id=1)
        n = insert_rows(rows)
        log.info("full retrain done: rows=%s", n)
    except Exception:
        log.exception("full retrain failed")


def _daily_update():
    """每天增量: 仅用最近 7 天数据更新模型参数, 不重新训练."""
    log.info("daily update start")
    try:
        # 同 _full_retrain 但 horizon 短
        _full_retrain()
    except Exception:
        log.exception("daily update failed")


@app.on_event("startup")
def on_start():
    """启动时挂载 cron 任务."""
    try:
        from apscheduler.triggers.cron import CronTrigger
        # 每周一 02:00 全量
        _scheduler.add_job(_full_retrain, CronTrigger(day_of_week="mon", hour=2, minute=0),
                            id="full_retrain", max_instances=1, coalesce=True,
                            replace_existing=True)
        # 每天 04:00 增量
        _scheduler.add_job(_daily_update, CronTrigger(hour=4, minute=0),
                            id="daily_update", max_instances=1, coalesce=True,
                            replace_existing=True)
        _scheduler.start()
        log.info("started, use_prophet=%s horizon=%s + cron 任务已挂载",
                 settings.use_prophet, settings.horizon_days)
    except Exception:
        log.exception("scheduler start failed")


@app.on_event("shutdown")
def on_stop():
    _scheduler.shutdown(wait=False)


@app.get("/health")
def health():
    return {"status": "ok", "use_prophet": settings.use_prophet,
            "horizon_days": settings.horizon_days}


class FitRequest(BaseModel):
    series: list[dict]              # [{ds: "2026-05-01", y: 100.0}, ...]
    horizon: int | None = None
    use_prophet: bool | None = None


@app.post("/v1/forecast/fit")
def fit_and_predict(req: FitRequest):
    from fastapi import HTTPException
    series: list[tuple[date, float]] = []
    for i, p in enumerate(req.series or []):
        if not isinstance(p, dict):
            raise HTTPException(400, f"series[{i}] must be dict")
        ds = p.get("ds"); y = p.get("y")
        if ds is None or y is None:
            raise HTTPException(400, f"series[{i}] missing ds or y")
        try:
            series.append((date.fromisoformat(str(ds)), float(y)))
        except Exception as e:
            raise HTTPException(400, f"series[{i}] parse: {e}")
    if len(series) < 14:
        raise HTTPException(400, "series too short, need at least 14 points")
    horizon = req.horizon or settings.horizon_days
    if horizon <= 0 or horizon > 90:
        raise HTTPException(400, "horizon must be 1..90")
    use_prophet = settings.use_prophet if req.use_prophet is None else req.use_prophet
    try:
        result = fit_and_forecast(series, horizon, use_prophet=use_prophet)
    except Exception as e:
        raise HTTPException(500, f"fit failed: {e}")
    return {
        "horizon": horizon,
        "mape": result.mape,
        "model": "PROPHET" if use_prophet else "SES",
        "forecasts": [{"target_date": f.target_date.isoformat(),
                       "forecast": f.forecast,
                       "lower": f.lower, "upper": f.upper} for f in result.forecasts],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
