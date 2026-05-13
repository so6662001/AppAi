"""轻量复用 dsl-compiler 的 metric registry, 用来取同义词."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import yaml


def load_synonyms(metrics_dir: Path) -> tuple[list[str], dict[str, str]]:
    """返回 (synonyms_flat, syn_to_metric).

    - synonyms_flat: 同义词扁平列表(用于意图匹配)
    - syn_to_metric: 同义词→指标 name 映射
    """
    flat: list[str] = []
    mp: dict[str, str] = {}

    for f in sorted(metrics_dir.glob("metrics_*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for m in data.get("metrics", []) or []:
            name = m.get("name")
            label = m.get("label")
            syns = m.get("synonyms") or []
            entries = list(filter(None, [name, label] + syns))
            for e in entries:
                e = str(e)
                if e not in mp:
                    flat.append(e)
                    mp[e] = name
    return flat, mp
