"""加载 metrics/*.yaml 到内存索引。"""
from __future__ import annotations
from pathlib import Path
from typing import Optional
import yaml

from .models import MetricDef


class MetricRegistry:
    """从 YAML 加载并提供按 name/code/synonyms 的查找。"""

    def __init__(self):
        self._by_name: dict[str, MetricDef] = {}
        self._by_code: dict[str, MetricDef] = {}
        self._by_synonym: dict[str, str] = {}
        self.dimensions: dict[str, dict] = {}
        self.common: dict = {}

    def add(self, m: MetricDef) -> None:
        self._by_name[m.name] = m
        if m.code:
            self._by_code[m.code] = m
        if m.alias:
            self._by_name[m.alias] = m
        for syn in m.synonyms or []:
            self._by_synonym[syn.lower()] = m.name

    def get(self, key: str) -> Optional[MetricDef]:
        if key in self._by_name:
            return self._by_name[key]
        if key in self._by_code:
            return self._by_code[key]
        syn = self._by_synonym.get(key.lower())
        if syn:
            return self._by_name.get(syn)
        return None

    def list_by_domain(self, domain: str) -> list[MetricDef]:
        return [m for m in self._by_name.values() if (m.domain or "").upper() == domain.upper()]

    def all_metrics(self) -> list[MetricDef]:
        return list(self._by_name.values())

    def __len__(self):
        return len(self._by_name)


def load_registry(metrics_dir: Path | str) -> MetricRegistry:
    metrics_dir = Path(metrics_dir)
    reg = MetricRegistry()

    common_file = metrics_dir / "_common.yaml"
    if common_file.exists():
        reg.common = yaml.safe_load(common_file.read_text(encoding="utf-8")) or {}

    dim_file = metrics_dir / "_dimensions.yaml"
    if dim_file.exists():
        data = yaml.safe_load(dim_file.read_text(encoding="utf-8")) or {}
        reg.dimensions = data.get("dimensions", {})

    for yaml_file in sorted(metrics_dir.glob("metrics_*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        domain = data.get("domain")
        for item in data.get("metrics", []) or []:
            try:
                m = MetricDef.model_validate(item)
            except Exception as e:
                # 跳过格式错误的条目, 不阻塞其他指标
                print(f"[registry] skip {item.get('name')}: {e}")
                continue
            if domain and not m.domain:
                m.domain = domain
            reg.add(m)

    return reg
