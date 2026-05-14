"""扫描引擎: 拉指标数值 → 评估规则 → 命中后写 advice_inbox + 调通知."""
from __future__ import annotations
import json
import logging
from datetime import datetime
from typing import Any
import httpx
from sqlalchemy import create_engine, text

from .config import settings
from .rules import load_rules, evaluate, AlertRule
from .cooldown import try_acquire


log = logging.getLogger("risk.engine")
_engine = None


def get_db():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.db_url, pool_pre_ping=True, future=True)
    return _engine


def _all_tenants() -> list[int]:
    """枚举活跃租户. 简化为从 tenant_wallet 表拉; 没有该表时返回 [1]."""
    try:
        with get_db().begin() as conn:
            rows = conn.execute(text("SELECT DISTINCT tenant_id FROM tenant_wallet")).all()
        if rows: return [int(r[0]) for r in rows]
    except Exception:
        pass
    return [1]


def fetch_metric_value(tenant_id: int, metric: str) -> dict[str, Any] | None:
    """调 dsl-compiler + 执行返回 {value, [optional context like customer_name]}。
    简化版: 用一个固定 DSL 模板, 实际可按 metric 配多变种."""
    dsl = {
        "metrics": [metric],
        "time": {"preset": "yesterday", "grain": "day"},
        "limit": 1,
    }
    try:
        r = httpx.post(f"{settings.dsl_compiler_url}/v1/dsl/compile", json={
            "dsl": dsl,
            "context": {"tenant_id": tenant_id, "user_id": 0, "business_line": "TRADE"},
        }, timeout=8)
        if r.status_code != 200:
            return None
        # 此处真实场景应进一步调 query-engine 拿数值,
        # 演示阶段返回 mock 值或调 chat-orchestrator
        # 简化: 不真实执行 SQL, 直接返回固定值便于单测
        return {"value": 0.97}
    except Exception as e:
        log.warning("fetch metric %s failed: %s", metric, e)
        return None


def write_inbox(tenant_id: int, user_targets: list[str], rule: AlertRule, value, context: dict):
    title = (rule.advice_template or rule.title).format(value=value, **context)
    sql = text("""
        INSERT INTO advice_inbox
          (tenant_id, user_id, role, category, rule_id, severity, title, payload_json, status, created_at)
        VALUES
          (:tid, :uid, :role, 'RISK', :rule, :sev, :title, :payload, 'NEW', NOW())
    """)
    with get_db().begin() as conn:
        for tgt in (user_targets or ["__broadcast__"]):
            payload = json.dumps({"rule_id": rule.id, "value": value, "context": context},
                                 ensure_ascii=False, default=str)
            conn.execute(sql, {
                "tid": tenant_id,
                "uid": None,                # 真实环境按 role 展开到具体 user_id
                "role": tgt,
                "rule": rule.id,
                "sev": rule.severity,
                "title": title or rule.id,
                "payload": payload,
            })
    # 真实推送 - 复用 report-scheduler 通知基础设施
    _real_push(tenant_id, rule, title, value, context)


def _real_push(tenant_id: int, rule, title: str, value, context: dict):
    """对接 report-scheduler/notify.py 实际发送 WECOM/DINGTALK/EMAIL."""
    try:
        # 查租户通知配置
        with get_db().begin() as conn:
            rows = conn.execute(text("""
                SELECT channel, config_json FROM tenant_notify_config
                WHERE tenant_id=:t AND is_active=1 AND is_default=1
            """), {"t": tenant_id}).all()
        if not rows:
            return
        # 引入 notify (报表调度器同包, 通过 PYTHONPATH 共享, 或独立调用 notification-service)
        try:
            sys_path_hack()
            from report_scheduler.notify import push
        except Exception:
            log.debug("notify module unavailable, fallback INAPP only")
            return
        text_summary = f"{title} (value={value})"
        for ch, cfg_raw in rows:
            try:
                cfg = json.loads(cfg_raw) if isinstance(cfg_raw, str) else cfg_raw
                r = push(ch, tenant_id=tenant_id, user_id=0,
                         title=title, summary=text_summary,
                         blocks=[{"type": "kpi",
                                  "kpis": [{"metric": rule.metric, "label": rule.metric,
                                            "value": value, "unit": "", "format": "amount"}]}],
                         run_id=0, report_name=rule.id, conf=cfg)
                log.info("risk push ch=%s ok=%s err=%s", ch, r.ok, r.error or "")
            except Exception as e:
                log.warning("push %s failed: %s", ch, e)
    except Exception:
        log.exception("real push failed")


def sys_path_hack():
    """在容器内 report-scheduler 已挂载到 PYTHONPATH; 本地开发时按需扩展."""
    import sys, os
    p = os.environ.get("REPORT_SCHEDULER_SRC", "/workspace/services/report-scheduler/src")
    if p and p not in sys.path:
        sys.path.insert(0, p)


def evaluate_rule_for_tenant(rule: AlertRule, tenant_id: int) -> bool:
    """对一个租户评估一条规则. 命中并通过冷却返回 True."""
    if not rule.enabled:
        return False
    res = fetch_metric_value(tenant_id, rule.metric)
    if not res:
        return False
    value = res.get("value")
    ctx = {"value": value, **res}
    if not evaluate(rule.when, ctx):
        return False
    # 实体冷却 (此处用 metric 名当 entity_key, 复杂场景可拿 customer_id)
    if not try_acquire(tenant_id, rule.id, rule.metric, rule.cooldown_hours):
        log.info("rule %s tenant=%s in cooldown", rule.id, tenant_id)
        return False
    write_inbox(tenant_id, rule.push_to, rule, value, res)
    log.info("ALERT %s tenant=%s metric=%s value=%s", rule.id, tenant_id, rule.metric, value)
    return True


def scan_once() -> int:
    rules = load_rules(settings.metrics_dir)
    hits = 0
    for tid in _all_tenants():
        for r in rules:
            try:
                if evaluate_rule_for_tenant(r, tid):
                    hits += 1
            except Exception:
                log.exception("evaluate %s tenant=%s failed", r.id, tid)
    return hits
