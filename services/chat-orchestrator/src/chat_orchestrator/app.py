"""FastAPI 入口 - 提供 SSE /v1/chat/messages."""
from __future__ import annotations
import json
import logging
import os
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from .config import settings
from .orchestrator import stream


logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("chat.app")


app = FastAPI(title="Chat Orchestrator", version="0.1.0")
app.add_middleware(CORSMiddleware,
                   allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatMessageReq(BaseModel):
    sessionId: str | None = None
    text: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/chat/messages")
async def chat(req: ChatMessageReq, request: Request):
    tenant_id = int(request.headers.get("X-Tenant-Id", "1"))
    user_id = int(request.headers.get("X-User-Id", "1"))
    business_line = request.headers.get("X-Business-Line", "TRADE")

    async def gen() -> AsyncIterator[dict]:
        async for ev in stream(
            text=req.text,
            tenant_id=tenant_id, user_id=user_id,
            business_line=business_line,
            session_id=req.sessionId,
        ):
            yield {
                "event": ev["event"],
                "data": json.dumps(ev["data"], ensure_ascii=False, default=str),
            }
    return EventSourceResponse(gen())


@app.post("/v1/chat/preview")
async def preview(req: ChatMessageReq, request: Request):
    """非流式版本, 一次性返回结果. 调试与单元测试用."""
    tenant_id = int(request.headers.get("X-Tenant-Id", "1"))
    user_id = int(request.headers.get("X-User-Id", "1"))
    events = []
    async for ev in stream(req.text, tenant_id, user_id):
        events.append({"event": ev["event"], "data": ev["data"]})
    return {"events": events}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
