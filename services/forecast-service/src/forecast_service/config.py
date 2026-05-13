from __future__ import annotations
import os
from pydantic import BaseModel


class Settings(BaseModel):
    sr_jdbc_url: str = os.environ.get("SR_JDBC_URL", "jdbc:mysql://localhost:9030/steel_dw")
    sr_user: str = os.environ.get("SR_USER", "root")
    sr_pass: str = os.environ.get("SR_PASS", "")
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", 8400))
    use_prophet: bool = os.environ.get("USE_PROPHET", "false").lower() == "true"
    horizon_days: int = int(os.environ.get("FORECAST_HORIZON", 7))
    full_retrain_cron: str = os.environ.get("FULL_RETRAIN_CRON", "0 2 * * 1")  # 每周一 02:00
    daily_update_cron: str = os.environ.get("DAILY_UPDATE_CRON", "0 4 * * *")  # 每天 04:00


settings = Settings()
