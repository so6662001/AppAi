"""执行器: 编译 DSL → 执行 SQL → 渲染 → 推送。

为避免直连 StarRocks 的复杂性, 这里通过 dsl-compiler HTTP API 拿到 SQL,
真实执行可以走两种方式:
  1) 调一个统一的 query-engine 服务 (推荐)
  2) 这里用 pymysql 直接连 StarRocks 9030 端口执行 (简化)
本骨架采用方案 2 简化, 留 hook 切方案 1。
"""
from __future__ import annotations
import json
import time
import json
import logging
from datetime import datetime
from typing import Any
import httpx

from .config import settings
from .db import (
    insert_run, update_run, update_report_next_run, write_chat_message, get_report_subscribers
)
from .cron import next_run_at
from .notify import push, NotifyResult
from .tenant_config import get_config as get_tenant_config
import os


log = logging.getLogger("scheduler.executor")


CHAT_ORCHESTRATOR_URL = os.environ.get("CHAT_ORCHESTRATOR_URL", "")


def execute_report(report: dict) -> None:
    """主流程: 一个报表的一次执行."""
    report_id = report["report_id"]
    tenant_id = report["tenant_id"]
    user_id   = report["user_id"]
    scheduled_at = report.get("next_run_at") or datetime.utcnow()
    started = datetime.utcnow()

    run_id = insert_run(report_id, tenant_id, scheduled_at, "RUNNING")
    log.info("execute report=%s run=%s tenant=%s", report_id, run_id, tenant_id)

    try:
        # 优先: 调 chat-orchestrator 拿渲染好的 blocks + AI 总结 (#18)
        if CHAT_ORCHESTRATOR_URL:
            try:
                co_result = _exec_via_chat(report, tenant_id, user_id)
                if co_result:
                    blocks, summary, sql_text, rows, biz_tokens = co_result
                    _finalize_success(run_id, report_id, started, sql_text, rows, blocks,
                                       summary, biz_tokens, tenant_id, user_id)
                    return
            except Exception as e:
                log.warning("chat orchestrator path failed, fallback to direct SQL: %s", e)

        # Fallback: 直接编译 + 执行 + 本地渲染
        # 1) 编译 DSL
        sql_text, params, biz_tokens = _compile(report["dsl_json"], tenant_id, user_id)

        # 2) 执行 SQL
        rows = _run_sql(sql_text, params)

        # 3) 渲染 blocks
        blocks, summary = _render(report, rows)

        # (后续步骤 4-7 移到 _finalize_success)

        _finalize_success(run_id, report_id, started, sql_text, rows, blocks,
                          summary, biz_tokens, tenant_id, user_id, report=report)
    except Exception as e:
        log.exception("execute failed report=%s", report_id)
        update_run(run_id,
                   finished_at=datetime.utcnow(),
                   duration_ms=int((datetime.utcnow() - started).total_seconds() * 1000),
                   status="FAILED",
                   error_code=type(e).__name__,
                   error_msg=str(e)[:1000])
        new_fail = int(report.get("fail_count") or 0) + 1
        nxt = next_run_at(report.get("cron_expr"), report.get("schedule_type"),
                          datetime.utcnow(), report.get("timezone") or settings.tz)
        update_report_next_run(report_id, next_run_at=nxt, last_run_at=datetime.utcnow(),
                                fail_count=new_fail)


# -------- 内部辅助 --------

def _exec_via_chat(report: dict, tenant_id: int, user_id: int):
    """通过 chat-orchestrator 拿渲染好的 blocks + AI 总结. 返回 None 表示失败."""
    dsl = report["dsl_json"]
    # 把 DSL 转成自然语言提示, 让 chat-orchestrator 走完整流程
    text_prompt = report.get("question") or f"定时报表: {report.get('name', '')}"
    try:
        r = httpx.post(f"{CHAT_ORCHESTRATOR_URL}/v1/chat/preview", json={
            "text": text_prompt,
            "sessionId": f"scheduled-{report['report_id']}",
        }, headers={
            "X-Tenant-Id": str(tenant_id),
            "X-User-Id": str(user_id),
        }, timeout=30)
        r.raise_for_status()
        events = r.json().get("events", [])
        blocks = []
        summary_parts = []
        sql_text = ""
        rows = []
        biz_tokens = 0
        for ev in events:
            t = ev["event"]; d = ev["data"]
            if t == "data":
                blocks.append(d)
            elif t == "token":
                summary_parts.append(d if isinstance(d, str) else json.dumps(d))
            elif t == "usage":
                biz_tokens = (d if isinstance(d, dict) else {}).get("bizTokensCharged", 0) or 0
            elif t == "status" and isinstance(d, dict) and "dsl" in d:
                pass
        return blocks, "".join(summary_parts), sql_text, rows, biz_tokens
    except Exception as e:
        log.warning("chat orchestrator call failed: %s", e)
        return None


def _finalize_success(run_id, report_id, started, sql_text, rows, blocks, summary,
                      biz_tokens, tenant_id, user_id, report=None):
    """成功执行后的统一收尾: 写 chat_message + 推送 + 落库 + 算下次时间."""
    msg_id = write_chat_message(
        tenant_id=tenant_id, user_id=user_id,
        session_id=f"scheduled-{report_id}",
        blocks=blocks, summary=summary, report_id=report_id,
    )
    push_results = _notify_all(report or {"report_id": report_id, "tenant_id": tenant_id,
                                            "user_id": user_id, "channels": ["INAPP"]},
                                run_id, summary, blocks)
    status = "SUCCESS" if rows else ("EMPTY" if not (report or {}).get("push_silent_if_empty") else "SUCCESS")
    update_run(run_id,
               finished_at=datetime.utcnow(),
               duration_ms=int((datetime.utcnow() - started).total_seconds() * 1000),
               status=status,
               sql_text=sql_text,
               rows_returned=len(rows),
               blocks_json=blocks,
               result_summary=summary,
               push_results=[r.to_dict() for r in push_results],
               biz_tokens_charged=biz_tokens,
               message_id=msg_id)
    if report:
        nxt = next_run_at(report.get("cron_expr"), report.get("schedule_type"),
                          datetime.utcnow(), report.get("timezone") or settings.tz)
        update_report_next_run(report_id, next_run_at=nxt, last_run_at=datetime.utcnow(),
                                fail_count=0)


def _compile(dsl: dict, tenant_id: int, user_id: int) -> tuple[str, dict, int]:
    """调 dsl-compiler 拿到 SQL + 参数 + 估算 token。"""
    r = httpx.post(f"{settings.dsl_compiler_url}/v1/dsl/compile", json={
        "dsl": dsl,
        "context": {"tenant_id": tenant_id, "user_id": user_id,
                    "business_line": "TRADE"}      # 后续从 user 拉
    }, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data["sql"], data.get("params", {}), int(data.get("biz_token_estimate", 0))


def _run_sql(sql_text: str, params: dict) -> list[dict]:
    """在 StarRocks 上执行 (用 pymysql)。
    生产推荐改为调 query-engine HTTP 服务, 集中权限/审计/缓存。"""
    try:
        import pymysql
    except ImportError:
        log.warning("pymysql 未安装, 跳过真实执行, 返回空")
        return []

    # 把 :p1 → %(p1)s
    safe = sql_text
    for k in params:
        safe = safe.replace(f":{k}", f"%({k})s")

    # 解析连接信息从 jdbc url
    # jdbc:mysql://host:port/db
    jdbc = settings.sr_jdbc_url
    host, port, db = "localhost", 9030, "steel_dw"
    try:
        rest = jdbc.replace("jdbc:mysql://", "")
        hp, db = rest.split("/", 1)
        host, port = hp.split(":")
        port = int(port)
    except Exception:
        pass

    try:
        conn = pymysql.connect(host=host, port=port, user=settings.sr_user,
                               password=settings.sr_password, db=db, charset="utf8mb4",
                               cursorclass=pymysql.cursors.DictCursor, connect_timeout=5)
    except Exception as e:
        log.warning("StarRocks 连接失败(可能未起): %s, 跳过执行", e)
        return []

    try:
        with conn.cursor() as cur:
            cur.execute(safe, params)
            return list(cur.fetchall())
    finally:
        conn.close()


def _render(report: dict, rows: list[dict]) -> tuple[list[dict], str]:
    """把 rows 渲染成给前端展示的 blocks + 文本摘要。

    简化处理: 主要支持 kpi/table 两种 block。
    生产建议改为调 AI 服务用便宜模型生成更人话的总结。
    """
    blocks: list[dict] = []
    if not rows:
        return blocks, f"【{report.get('name','')}】今日无数据"

    # 1) KPI: 第一行的指标列
    first = rows[0]
    kpis = []
    for k, v in first.items():
        if isinstance(v, (int, float)):
            kpis.append({"metric": k, "label": k, "value": v, "unit": "", "format": "amount"})
    if kpis:
        blocks.append({"type": "kpi", "kpis": kpis[:4]})

    # 2) 表格
    if len(rows) > 1:
        blocks.append({
            "type": "table",
            "columns": list(rows[0].keys()),
            "rows": rows[:100],
        })

    summary = f"【{report.get('name','')}】数据已生成, 共 {len(rows)} 行"
    return blocks, summary


def _notify_all(report: dict, run_id: int, summary: str, blocks: list) -> list[NotifyResult]:
    """对所有 recipients × channels 推送。"""
    out: list[NotifyResult] = []
    channels = report.get("channels") or ["INAPP"]
    # 默认通知给 user_id 自己
    recipients = report.get("recipients") or [f"user:{report['user_id']}"]

    # 拉订阅者
    subs = get_report_subscribers(report["report_id"])
    for s in subs:
        recipients.append(f"user:{s['subscriber_user_id']}")

    seen = set()
    tenant_id = report["tenant_id"]
    for r in recipients:
        if not r.startswith("user:"):
            continue                # role/department 由通知服务展开, 此处略
        uid = int(r.split(":", 1)[1])
        if uid in seen: continue
        seen.add(uid)
        for ch in channels:
            # 拉租户级渠道配置 (webhook/SMTP/AppID 等)
            ch_conf = get_tenant_config(tenant_id, ch) if ch != "INAPP" else None
            res = push(ch,
                       tenant_id=tenant_id, user_id=uid,
                       title=report.get("name", "定时报表"),
                       summary=summary, blocks=blocks,
                       run_id=run_id, report_name=report.get("name", ""),
                       conf=ch_conf)
            out.append(res)
            log.info("push run=%s user=%s ch=%s ok=%s err=%s",
                     run_id, uid, ch, res.ok, res.error or "")
    return out
