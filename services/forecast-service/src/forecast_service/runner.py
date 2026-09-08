"""把训练结果落到 dws_forecast_daily 表."""
from __future__ import annotations
import logging
from datetime import date
from typing import Optional

from .models import fit_and_forecast


log = logging.getLogger("forecast.runner")


def train_one_scope(scope_type: str, scope_id: str, metric_code: str,
                    history: list[tuple[date, float]], horizon: int,
                    use_prophet: bool, tenant_id: int,
                    run_date: date | None = None) -> list[dict]:
    """训练一个 scope, 返回准备写入 dws_forecast_daily 的行."""
    if len(history) < 14:
        log.info("skip %s/%s: history too short (%d)", scope_type, scope_id, len(history))
        return []
    run_date = run_date or date.today()
    result = fit_and_forecast(history, horizon, use_prophet=use_prophet)
    rows = []
    for f in result.forecasts:
        rows.append({
            "tenant_id": tenant_id,
            "run_date": run_date,
            "target_date": f.target_date,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "metric_code": metric_code,
            "forecast_value": float(f.forecast),
            "forecast_lower_90": float(f.lower),
            "forecast_upper_90": float(f.upper),
            "model_name": "PROPHET" if use_prophet else "SES",
            "model_version": "0.1",
            "mape_30d": float(result.mape),
        })
    return rows


def insert_rows(rows: list[dict], conn_factory=None) -> int:
    """批量写 StarRocks dws_forecast_daily.
    conn_factory: () -> pymysql.connection; 不传时尝试默认连本地 StarRocks."""
    if not rows: return 0
    try:
        if conn_factory is None:
            import pymysql
            from .config import settings
            jdbc = settings.sr_jdbc_url.replace("jdbc:mysql://", "")
            hp, db = jdbc.split("/", 1)
            host, port = hp.split(":")
            conn = pymysql.connect(host=host, port=int(port), user=settings.sr_user,
                                   password=settings.sr_pass, db=db, charset="utf8mb4",
                                   connect_timeout=3)
        else:
            conn = conn_factory()
    except Exception as e:
        log.warning("DB connect failed, skip write: %s", e)
        return 0

    try:
        cols = ["tenant_id", "run_date", "target_date", "scope_type", "scope_id",
                "metric_code", "forecast_value", "forecast_lower_90", "forecast_upper_90",
                "model_name", "model_version", "mape_30d"]
        placeholders = ",".join(["%s"] * len(cols))
        sql = f"INSERT INTO dws_forecast_daily ({','.join(cols)}) VALUES ({placeholders})"
        with conn.cursor() as cur:
            cur.executemany(sql, [tuple(r[c] for c in cols) for r in rows])
        conn.commit()
        return len(rows)
    finally:
        try: conn.close()
        except Exception: pass
