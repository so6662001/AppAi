"""RAG + 多模型路由 服务."""
from __future__ import annotations
import logging
import os
import yaml
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

from .store import VectorStore
from . import router as model_router


logging.basicConfig(level="INFO")
log = logging.getLogger("rag")


app = FastAPI(title="RAG Service", version="0.1.0")
_store = VectorStore()


@app.on_event("startup")
def on_start():
    """启动时把 metrics/*.yaml 的指标 label+notes+synonyms 离线 embed."""
    metrics_dir = Path(os.environ.get("METRICS_DIR", "/workspace/metrics"))
    count = 0
    for f in sorted(metrics_dir.glob("metrics_*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        for m in data.get("metrics", []) or []:
            name = m.get("name", "")
            label = m.get("label", "")
            note = m.get("note") or m.get("notes") or ""
            syns = " ".join(m.get("synonyms") or [])
            text = f"{label} {name} {syns} {note}"
            _store.upsert(doc_id=name, text=text, meta={
                "label": label, "domain": m.get("domain"),
                "code": m.get("code"), "synonyms": m.get("synonyms") or [],
            })
            count += 1
    log.info("loaded %s metric docs into RAG store", count)


@app.get("/health")
def health(): return {"status": "ok", "docs_loaded": _store.size()}


class SearchReq(BaseModel):
    query: str
    top_k: int = 5


@app.post("/v1/rag/search")
def search(req: SearchReq):
    return {"results": _store.search(req.query, req.top_k)}


@app.get("/v1/router")
def router_pick(task: str, text_length: int = 0, complex_hint: bool = False):
    r = model_router.route(task, text_length, complex_hint)
    return {"provider": r.provider, "model": r.model, "why": r.why}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 8950)))
