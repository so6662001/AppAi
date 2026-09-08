"""加载 role_insights/*.yaml -> RoleProfileDef."""
from __future__ import annotations
import os
from pathlib import Path
import yaml

from .models import RoleProfileDef, KpiDef, RuleDef, ActionItem

PROFILE_DIR = Path(os.environ.get("ROLE_INSIGHTS_DIR", "/workspace/role_insights"))

_cache: dict[str, RoleProfileDef] = {}


def load_all() -> dict[str, RoleProfileDef]:
    """加载所有 yaml 进缓存."""
    _cache.clear()
    if not PROFILE_DIR.exists():
        return _cache
    for f in sorted(PROFILE_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception as e:
            print(f"WARN: skip bad yaml {f}: {e}")
            continue
        if "role_code" not in data:
            continue
        prof = _parse(data)
        _cache[prof.role_code] = prof
    return _cache


def get_profile(role_code: str) -> RoleProfileDef | None:
    if not _cache:
        load_all()
    return _cache.get(role_code)


def _parse(data: dict) -> RoleProfileDef:
    kpis = [KpiDef(**k) for k in (data.get("primary_kpis") or [])]
    rules = []
    for r in (data.get("rules") or []):
        actions = [ActionItem(**a) for a in (r.get("actions") or [])]
        rules.append(RuleDef(
            id=r["id"], category=r.get("category","WEAKNESS"),
            severity=r.get("severity","MEDIUM"),
            title=r.get("title", r["id"]),
            when=r.get("when",""),
            finding=r.get("finding",""),
            impact=r.get("impact",""),
            actions=actions,
            score_impact=r.get("score_impact", 5),
        ))
    return RoleProfileDef(
        role_code=data["role_code"],
        role_name=data.get("role_name", data["role_code"]),
        business_line=data.get("business_line","ALL"),
        level=data.get("level","STAFF"),
        focus_areas=data.get("focus_areas") or [],
        primary_kpis=kpis,
        rules=rules,
        routines=data.get("routines") or [],
        education=data.get("education") or [],
    )
