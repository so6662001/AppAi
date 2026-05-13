"""把 Intent 转成 DSL JSON, 给 dsl-compiler 编译."""
from __future__ import annotations
from typing import Any
from .intent import Intent


def build_dsl(intent: Intent, syn_to_metric: dict[str, str]) -> dict:
    metrics = []
    for kw in intent.metrics_keywords:
        m = syn_to_metric.get(kw)
        if m and m not in metrics:
            metrics.append(m)
    # 必须至少 1 个指标, 否则默认销售额
    if not metrics:
        metrics = ["sales_amount"]
    if len(metrics) > 4:
        metrics = metrics[:4]                  # 控制成本

    dsl: dict[str, Any] = {
        "metrics": metrics,
        "dimensions": list(dict.fromkeys(intent.dimensions)),
        "filters": list(intent.filters or []),
        "time": {
            "preset": intent.time_preset or "yesterday",
            "grain": intent.grain or "day",
        },
        "limit": 100,
    }

    if intent.compare:
        dsl["compare"] = {"mode": intent.compare}

    if intent.top_n:
        # TopN 选第 1 个指标
        dsl["topN"] = {"by": metrics[0], "n": intent.top_n, "others": False}
        dsl["orderBy"] = [{"field": metrics[0], "dir": intent.order_dir}]
        dsl["limit"] = intent.top_n + 1
    return dsl
