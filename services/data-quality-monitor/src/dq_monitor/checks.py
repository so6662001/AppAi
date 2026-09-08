"""4 类数据质量检查."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class CheckResult:
    metric_code: str
    event_type: str        # FRESHNESS / NULL_RATIO / SPIKE / CONSISTENCY
    severity: str          # LOW / MEDIUM / HIGH / CRITICAL
    passed: bool
    detail: dict


def check_freshness(metric_code: str, last_update: datetime,
                    sla_minutes: int = 60) -> CheckResult:
    delta_min = (datetime.utcnow() - last_update).total_seconds() / 60
    passed = delta_min <= sla_minutes
    return CheckResult(metric_code, "FRESHNESS",
        "HIGH" if not passed else "LOW",
        passed, {"sla_minutes": sla_minutes, "actual_minutes": int(delta_min),
                 "last_update": last_update.isoformat()})


def check_null_ratio(metric_code: str, null_count: int, total_count: int,
                     threshold: float = 0.05) -> CheckResult:
    ratio = null_count / total_count if total_count > 0 else 0.0
    passed = ratio <= threshold
    return CheckResult(metric_code, "NULL_RATIO",
        "MEDIUM" if not passed else "LOW",
        passed, {"threshold": threshold, "actual": round(ratio, 4),
                 "null_count": null_count, "total_count": total_count})


def check_spike(metric_code: str, current_value: float, baseline: float,
                threshold_pct: float = 0.50) -> CheckResult:
    if baseline == 0:
        return CheckResult(metric_code, "SPIKE", "LOW", True,
                           {"baseline_zero": True})
    pct = abs(current_value - baseline) / abs(baseline)
    passed = pct <= threshold_pct
    return CheckResult(metric_code, "SPIKE",
        "MEDIUM" if not passed else "LOW",
        passed, {"baseline": baseline, "current": current_value,
                 "pct_change": round(pct, 4), "threshold_pct": threshold_pct})


def check_consistency(metric_code: str, parent_sum: float, child_sum: float,
                      tol: float = 0.001) -> CheckResult:
    diff = abs(parent_sum - child_sum)
    passed = (diff / max(abs(parent_sum), 1)) <= tol
    return CheckResult(metric_code, "CONSISTENCY",
        "HIGH" if not passed else "LOW",
        passed, {"parent": parent_sum, "child": child_sum, "diff": diff})
