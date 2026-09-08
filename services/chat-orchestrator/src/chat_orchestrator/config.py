"""配置."""
from __future__ import annotations
import os
from pathlib import Path
from pydantic import BaseModel


class Settings(BaseModel):
    metrics_dir: Path = Path(
        os.environ.get("METRICS_DIR", "/workspace/metrics"))
    dsl_compiler_url: str = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")
    billing_url: str = os.environ.get("BILLING_URL", "http://localhost:8081/api/v1")
    query_engine_url: str = os.environ.get("QUERY_ENGINE_URL", "http://localhost:8800")
    sr_jdbc_url: str = os.environ.get("SR_JDBC_URL", "jdbc:mysql://localhost:9030/steel_dw")
    sr_user: str = os.environ.get("SR_USER", "root")
    sr_pass: str = os.environ.get("SR_PASS", "")
    llm_provider: str = os.environ.get("LLM_PROVIDER", "rule")     # rule/deepseek/qwen/local
    llm_api_key: str | None = os.environ.get("LLM_API_KEY")
    llm_model: str | None = os.environ.get("LLM_MODEL")
    db_url: str = os.environ.get("DB_URL",
        "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4")
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", 8200))


settings = Settings()
