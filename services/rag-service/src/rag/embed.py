"""Embedding 接口.

生产: 调 bge-m3 本地 / OpenAI text-embedding-3-small / Aliyun text_embedding_v2
开发: 用简单 BoW + tf-idf 作为伪 embedding (测试用, 0 依赖)
"""
from __future__ import annotations
import math
import re
from typing import Iterable


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,.;!?，。；！？\-:：()（）]+", text or "") if t]


def embed_bow(text: str, dim: int = 256) -> list[float]:
    """简单 hash-based BoW embedding, 0 外部依赖, 用于测试与冷启动."""
    vec = [0.0] * dim
    for t in _tokenize(text):
        idx = hash(t) % dim
        vec[idx] += 1.0
    n = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x / n for x in vec]


def cosine(a: list[float], b: list[float]) -> float:
    s = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a)) or 1.0
    nb = math.sqrt(sum(y*y for y in b)) or 1.0
    return s / (na * nb)
