"""加载 metrics_risk.yaml 中的 alert_rules 段。

YAML 结构:
  alert_rules:
    - id: ALERT_CREDIT_OVER
      metric: credit_utilization_rate
      when: "value > 0.95"
      severity: HIGH
      title: "..."
      push_to: [客户经理, 风控, 老板]
      cooldown_hours: 12
      advice_template: "客户【{customer_name}】..."
"""
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class AlertRule:
    id: str
    metric: str
    when: str
    severity: str = "MEDIUM"
    title: str = ""
    push_to: list[str] = field(default_factory=list)
    cooldown_hours: int = 12
    advice_template: str = ""
    enabled: bool = True


def load_rules(metrics_dir: Path) -> list[AlertRule]:
    """从 metrics_risk.yaml + metrics_abc.yaml 等加载 alert_rules + action_rules."""
    out: list[AlertRule] = []
    for f in sorted(metrics_dir.glob("metrics_*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for r in (data.get("alert_rules") or []):
            try:
                out.append(AlertRule(
                    id=r["id"],
                    metric=r["metric"],
                    when=r.get("when", ""),
                    severity=r.get("severity", "MEDIUM"),
                    title=r.get("title", ""),
                    push_to=r.get("push_to", []),
                    cooldown_hours=int(r.get("cooldown_hours", 12)),
                    advice_template=r.get("advice_template", ""),
                ))
            except Exception:
                continue
    return out


# ============ 简化的"when" 表达式解析 ============
# 支持以下形式 (变量名 value, wow_change, mom_change, yoy_change 等):
#   value > 0.95
#   value >= hedge_position_limit       # 引用外部常量
#   wow_change > 0.05

_OPS = ["<=", ">=", "==", "!=", "<", ">"]


def evaluate(expr: str, ctx: dict) -> bool:
    """对单个原子表达式求值. 暂不支持 AND/OR 组合, 复杂表达式需走 Python eval(受限)."""
    if not expr:
        return False
    e = expr.strip()
    for op in _OPS:
        if op in e:
            left, right = e.split(op, 1)
            l = _resolve(left.strip(), ctx)
            r = _resolve(right.strip(), ctx)
            if l is None or r is None:
                return False
            try:
                lf, rf = float(l), float(r)
            except Exception:
                return False
            if op == "<":  return lf < rf
            if op == ">":  return lf > rf
            if op == "<=": return lf <= rf
            if op == ">=": return lf >= rf
            if op == "==": return lf == rf
            if op == "!=": return lf != rf
    return False


def _resolve(token: str, ctx: dict):
    if token in ctx:
        return ctx[token]
    # 数字字面量
    try:
        return float(token)
    except Exception:
        return None
