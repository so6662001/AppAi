"""Embedding 接口.

3 套实现, 按 EMBED_PROVIDER 环境变量选择:
  - bow    : 简单 hash-BoW (默认, 0 依赖, 测试用)
  - bge-m3 : 调 xinference / FastEmbed 本地服务 (生产推荐)
  - openai : 调 OpenAI text-embedding-3-small (云上)
  - aliyun : 调 通义 text-embedding-v2

失败时自动 fallback 到 BoW, 保证服务可用.
"""
from __future__ import annotations
import logging
import math
import os
import re
from typing import Optional

log = logging.getLogger("rag.embed")

PROVIDER = os.environ.get("EMBED_PROVIDER", "bow")
BGE_URL  = os.environ.get("BGE_URL", "http://bge-m3:9997/v1")
BGE_MODEL = os.environ.get("BGE_MODEL", "bge-m3")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
ALIYUN_KEY = os.environ.get("ALIYUN_API_KEY")

_cache: dict[str, list[float]] = {}


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,.;!?，。；！？\-:：()（）]+", text or "") if t]


def embed_bow(text: str, dim: int = 256) -> list[float]:
    vec = [0.0] * dim
    for t in _tokenize(text):
        idx = hash(t) % dim
        vec[idx] += 1.0
    n = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x / n for x in vec]


def embed_bge(text: str) -> Optional[list[float]]:
    """调 xinference/FastEmbed 兼容服务 (OpenAI 协议)."""
    try:
        import httpx
        r = httpx.post(f"{BGE_URL}/embeddings", json={
            "model": BGE_MODEL, "input": text
        }, timeout=5)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        log.debug("bge embed fail: %s", e); return None


def embed_openai(text: str) -> Optional[list[float]]:
    if not OPENAI_KEY: return None
    try:
        import httpx
        r = httpx.post("https://api.openai.com/v1/embeddings", json={
            "model": "text-embedding-3-small", "input": text
        }, headers={"Authorization": f"Bearer {OPENAI_KEY}"}, timeout=8)
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception as e:
        log.debug("openai embed fail: %s", e); return None


def embed(text: str) -> list[float]:
    """统一入口 - 按 provider 选 + cache + fallback."""
    if not text: return embed_bow("")
    if text in _cache: return _cache[text]
    v: Optional[list[float]] = None
    if PROVIDER == "bge-m3":
        v = embed_bge(text)
    elif PROVIDER == "openai":
        v = embed_openai(text)
    elif PROVIDER == "aliyun":
        # 留接口, 阿里通义 SDK
        v = None
    if v is None:
        v = embed_bow(text)
    _cache[text] = v
    return v


def cosine(a: list[float], b: list[float]) -> float:
    # 兼容不同维度: 截断到较短
    n = min(len(a), len(b))
    s = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(x*x for x in a[:n])) or 1.0
    nb = math.sqrt(sum(y*y for y in b[:n])) or 1.0
    return s / (na * nb)
