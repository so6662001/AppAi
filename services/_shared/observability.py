"""Prometheus 指标暴露 - 供各 FastAPI 服务复用.

使用:
    from observability import setup
    setup(app, service_name="chat-orchestrator")

会自动:
  - 暴露 GET /metrics (Prometheus 文本格式)
  - 记录 http_requests_total / http_request_duration_seconds
  - 记录 service_info{name=...}
"""
from __future__ import annotations
import time
from typing import Callable
try:
    from prometheus_client import Counter, Histogram, Info, generate_latest, CONTENT_TYPE_LATEST
    _ENABLED = True
except ImportError:
    _ENABLED = False


def setup(app, service_name: str = "unknown") -> None:
    if not _ENABLED:
        return

    info = Info("service", "Service info")
    info.info({"name": service_name, "version": "0.1.0"})

    REQUESTS = Counter(
        "http_requests_total", "HTTP requests",
        labelnames=["method", "path", "status"])
    LATENCY = Histogram(
        "http_request_duration_seconds", "HTTP latency",
        labelnames=["method", "path"])

    @app.middleware("http")
    async def metrics_mw(request, call_next):
        t0 = time.time()
        resp = await call_next(request)
        elapsed = time.time() - t0
        # 把路径模板化, 避免高基数 (例如 /v1/x/{id} 而非 /v1/x/123)
        path = request.scope.get("route").path if request.scope.get("route") else request.url.path
        REQUESTS.labels(request.method, path, resp.status_code).inc()
        LATENCY.labels(request.method, path).observe(elapsed)
        return resp

    from fastapi import Response
    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
