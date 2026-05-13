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
    """每周一全量重训. 简化版只 log."""
    log.info("full retrain triggered (placeholder)")


def _daily_update():
    log.info("daily incremental update triggered (placeholder)")


@app.on_event("startup")
def on_start():
    _scheduler.start()
    log.info("started, use_prophet=%s horizon=%s", settings.use_prophet, settings.horizon_days)


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
    series = [(date.fromisoformat(p["ds"]), float(p["y"])) for p in req.series]
    horizon = req.horizon or settings.horizon_days
    use_prophet = settings.use_prophet if req.use_prophet is None else req.use_prophet
    result = fit_and_forecast(series, horizon, use_prophet=use_prophet)
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
