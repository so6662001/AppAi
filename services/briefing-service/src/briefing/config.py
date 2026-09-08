from __future__ import annotations
import os
from pydantic import BaseModel


class Settings(BaseModel):
    db_url: str = os.environ.get("DB_URL",
        "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4")
    dsl_compiler_url: str = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")
    chat_url: str = os.environ.get("CHAT_URL", "http://localhost:8200")
    generate_cron: str = os.environ.get("BRIEFING_CRON", "0 5 * * *")  # 每天 05:00
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", 8500))


settings = Settings()
