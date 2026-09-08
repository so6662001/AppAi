"""向量库 - 内存版 (生产换 Milvus/pgvector)."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from .embed import embed, cosine


@dataclass
class Doc:
    doc_id: str
    text: str
    meta: dict = field(default_factory=dict)
    vec: list[float] = field(default_factory=list)


class VectorStore:

    def __init__(self):
        self._docs: list[Doc] = []

    def upsert(self, doc_id: str, text: str, meta: dict | None = None):
        v = embed(text)
        # 替换或追加
        for i, d in enumerate(self._docs):
            if d.doc_id == doc_id:
                self._docs[i] = Doc(doc_id, text, meta or {}, v); return
        self._docs.append(Doc(doc_id, text, meta or {}, v))

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        qv = embed(query)
        scored = [(cosine(qv, d.vec), d) for d in self._docs]
        scored.sort(key=lambda x: -x[0])
        return [{"doc_id": d.doc_id, "score": s, "text": d.text, "meta": d.meta}
                for s, d in scored[:top_k]]

    def size(self) -> int: return len(self._docs)
