"""配置 - 从环境变量加载。"""
from __future__ import annotations
import os
from pydantic import BaseModel


class Settings(BaseModel):
    # 数据库
    db_url: str = os.environ.get(
        "DB_URL",
        "mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4",
    )
    # StarRocks 查询(只读)
    sr_jdbc_url: str = os.environ.get("SR_JDBC_URL", "jdbc:mysql://localhost:9030/steel_dw")
    sr_user: str = os.environ.get("SR_USER", "etl_writer")
    sr_password: str = os.environ.get("SR_PASS", "")

    # DSL 编译器
    dsl_compiler_url: str = os.environ.get("DSL_COMPILER_URL", "http://localhost:8000")

    # 计费服务
    billing_url: str = os.environ.get("BILLING_URL", "http://localhost:8080/v1")

    # 通知服务
    notify_url: str = os.environ.get("NOTIFY_URL", "http://localhost:8080/v1/notify")

    # 调度配置
    scan_interval_seconds: int = int(os.environ.get("SCAN_INTERVAL", 30))
    max_concurrent_jobs: int = int(os.environ.get("MAX_CONCURRENT", 10))
    max_fail_count: int = int(os.environ.get("MAX_FAIL", 3))
    tz: str = os.environ.get("TZ", "Asia/Shanghai")

    # 健康检查
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", 8100))


settings = Settings()
