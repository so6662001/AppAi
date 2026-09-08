"""RAG store + router 测试."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from rag.store import VectorStore
from rag.embed import embed_bow, cosine
from rag import router as model_router


def test_embed_normalized():
    v = embed_bow("销售额 营收 产值")
    n2 = sum(x*x for x in v)
    assert abs(n2 - 1.0) < 1e-3 or n2 < 1e-6


def test_cosine_identical():
    a = embed_bow("销售额")
    assert cosine(a, a) > 0.99


def test_vector_store_search():
    s = VectorStore()
    s.upsert("sales_amount", "销售额 营收 产值")
    s.upsert("gross_profit", "毛利 销售毛利")
    s.upsert("oee", "OEE 设备综合效率")
    r = s.search("营收", top_k=2)
    assert r[0]["doc_id"] == "sales_amount"


def test_router_intent_uses_cheap_model():
    c = model_router.route("intent", text_length=20)
    assert c.provider in ("local", "deepseek", "qwen")
    assert c.model != "deepseek-reasoner"


def test_router_drill_uses_strong_model():
    c = model_router.route("drill", text_length=100)
    assert "reason" in c.model.lower() or "max" in c.model.lower()


def test_router_long_text_promoted():
    c = model_router.route("summarize", text_length=1200)
    assert "reason" in c.model.lower() or "max" in c.model.lower()
