from __future__ import annotations
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    db_url: str = os.environ.get("DB_URL",
        "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4")
    metrics_dir: Path = Path(os.environ.get("METRICS_DIR", "/workspace/metrics"))
    dsl_compiler_url: str = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")
    redis_host: str = os.environ.get("REDIS_HOST", "localhost")
    redis_port: int = int(os.environ.get("REDIS_PORT", 6379))
    scan_interval_sec: int = int(os.environ.get("SCAN_INTERVAL", 3600))   # 默认每小时
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", 8300))
    tz: str = os.environ.get("TZ", "Asia/Shanghai")


settings = Settings()
