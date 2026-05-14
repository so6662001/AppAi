"""FastAPI: POST /v1/query/execute"""
from __future__ import annotations
import os
from fastapi import FastAPI, Request
from pydantic import BaseModel
from . import executor


app = FastAPI(title="Query Engine", version="0.1.0")


class ExecuteReq(BaseModel):
    sql: str
    params: dict = {}
    no_cache: bool = False
    row_limit: int = 50000
    question: str | None = None      # 携带原始问题, 启用 L2 语义缓存


@app.get("/health")
def health(): return {"status": "ok"}


@app.post("/v1/query/execute")
def exec_query(req: ExecuteReq, request: Request):
    tid = int(request.headers.get("X-Tenant-Id", "1"))
    uid = int(request.headers.get("X-User-Id", "1"))
    return executor.execute(req.sql, req.params, tid, uid,
                            no_cache=req.no_cache, row_limit=req.row_limit,
                            question=req.question)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8800)))
