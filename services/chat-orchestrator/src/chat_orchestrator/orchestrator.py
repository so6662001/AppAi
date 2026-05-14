"""主编排: NL → 意图 → DSL → SQL → 渲染 → SSE chunks."""
from __future__ import annotations
import json
import logging
import time
import uuid
from typing import AsyncIterator
import httpx

from .config import settings
from .intent import detect, Intent
from .dsl_builder import build_dsl
from .registry_client import load_synonyms
from .renderer import render
from .llm import LLMClient
from . import session as session_db
from . import billing_client


log = logging.getLogger("chat.orchestrator")

# 启动时加载一次同义词
_SYN_FLAT, _SYN_TO_METRIC = load_synonyms(settings.metrics_dir)

# LLM 客户端
_llm = LLMClient(provider=settings.llm_provider,
                 api_key=settings.llm_api_key,
                 model=settings.llm_model)


async def stream(text: str, tenant_id: int, user_id: int, business_line: str = "TRADE",
                 session_id: str | None = None) -> AsyncIterator[dict]:
    """SSE 事件生成器, yield dict {event, data}."""
    msg_id = uuid.uuid4().hex

    # 会话持久化
    if not session_id:
        session_id = session_db.new_session_id()
    session_db.ensure_session(session_id, tenant_id, user_id, business_line=business_line,
                              title=text[:30] if text else None)
    user_msg_id = session_db.save_user_message(session_id, tenant_id, user_id, text)

    # 预扣费 (失败也继续, 由 sweeper 兜底)
    reservation_id = billing_client.preauth(tenant_id, user_id, session_id, msg_id, estimate=500)

    # 1. 意图 + 槽位
    yield {"event": "status", "data": {"phase": "parsing"}}
    intent = detect(text, _SYN_FLAT)

    # LLM 兜底: 规则未命中任何指标时调 LLM 抽取
    if not intent.metrics_keywords and _llm.enabled:
        llm_intent = _llm.intent_extract(text, list(_SYN_TO_METRIC.values()))
        if llm_intent:
            # 把 LLM 输出的指标名当成"同义词"塞回 intent
            for m in (llm_intent.get("metrics") or []):
                if m in _SYN_TO_METRIC.values():
                    # 找到原始 syn key
                    for k, v in _SYN_TO_METRIC.items():
                        if v == m and k not in intent.metrics_keywords:
                            intent.metrics_keywords.append(k); break
            if llm_intent.get("time_preset"): intent.time_preset = llm_intent["time_preset"]
            for d in (llm_intent.get("dimensions") or []):
                if d not in intent.dimensions: intent.dimensions.append(d)
            if llm_intent.get("compare"): intent.compare = llm_intent["compare"]
            if llm_intent.get("top_n"):   intent.top_n = int(llm_intent["top_n"])
    yield {"event": "meta", "data": {
        "messageId": msg_id, "intent": intent.type,
        "metricsMatched": intent.metrics_keywords,
        "time": intent.time_preset, "compare": intent.compare,
    }}

    # 2. 构造 DSL
    dsl = build_dsl(intent, _SYN_TO_METRIC)
    yield {"event": "status", "data": {"phase": "compiling", "dsl": dsl}}

    # 3. 调 dsl-compiler 编译 SQL
    try:
        async with httpx.AsyncClient(timeout=10) as cli:
            r = await cli.post(f"{settings.dsl_compiler_url}/v1/dsl/compile", json={
                "dsl": dsl,
                "context": {"tenant_id": tenant_id, "user_id": user_id,
                            "business_line": business_line},
            })
            r.raise_for_status()
            compiled = r.json()
    except Exception as e:
        log.exception("compile failed")
        yield {"event": "error", "data": {"code": "E_COMPILE", "message": str(e)}}
        return

    yield {"event": "status", "data": {"phase": "querying", "tables": compiled.get("tables_used")}}

    # 4. 执行 SQL (优先 query-engine, 失败 fallback 直连, 再失败明确告知用户)
    rows, exec_meta = _execute_sql_safe(compiled.get("sql") or "",
                                         compiled.get("params") or {},
                                         tenant_id, user_id, text)
    if exec_meta.get("degraded") and exec_meta.get("mode") == "demo":
        # 给用户明确告知降级 - 不静默欺骗用户
        yield {"event": "warning", "data": {
            "code": "W_DATA_UNAVAILABLE",
            "message": "数据源不可用, 当前展示的是演示数据, 仅供 UI 体验",
        }}

    # 5. 渲染 blocks
    blocks, base_summary = render(rows, dsl)
    # 5b. LLM 优化总结 (失败时 fallback 原生)
    summary = _llm.summarize(rows, dsl, base_summary) if _llm.enabled else base_summary
    for b in blocks:
        yield {"event": "data", "data": b}

    # 6. 流式输出总结
    for chunk in _tokenize(summary):
        yield {"event": "token", "data": chunk}
        time.sleep(0.005)

    # 7. 下钻建议
    drilldowns = _drilldown_suggestions(intent, dsl)
    if drilldowns:
        yield {"event": "drilldown_suggestion", "data": drilldowns}

    # 8. 用量上报 (含 reservation 预估)
    usage = {
        "inputTokens": len(text) // 2,
        "outputTokens": len(summary) // 2,
        "queryRows": len(rows),
        "cacheHit": False,
        "bizTokensCharged": compiled.get("biz_token_estimate") or 200,
        "bucket": "MIX",
    }
    yield {"event": "usage", "data": usage}

    # 持久化 assistant 消息
    session_db.save_assistant_message(
        session_id=session_id, tenant_id=tenant_id,
        msg_id=msg_id, blocks=blocks, summary=summary, dsl=dsl,
        sql_text=compiled.get("sql"),
        metrics_used=compiled.get("metrics_expanded") or [],
        usage=usage,
        model_name=(settings.llm_model or settings.llm_provider),
        parent_message_id=user_msg_id,
    )

    # 实际计费结算
    billing_client.settle(tenant_id, reservation_id,
                          actual=usage["bizTokensCharged"],
                          model_name=settings.llm_model or settings.llm_provider,
                          input_tokens=usage["inputTokens"],
                          output_tokens=usage["outputTokens"],
                          query_rows=usage["queryRows"], cache_hit=False)

    yield {"event": "done", "data": {"messageId": msg_id, "sessionId": session_id}}


def _execute_sql_safe(sql: str, params: dict, tenant_id: int, user_id: int,
                      question: str) -> tuple[list[dict], dict]:
    """三层降级:
       1) 调 query-engine (带 L1/L2 缓存 + 审计 + 行限制)
       2) 直连 StarRocks (pymysql) - 已不推荐
       3) 真不可达时返回 demo, **并返回 degraded=True 让上层告知用户**
    """
    # 1) query-engine
    if not sql:
        return [], {"mode": "no_sql"}
    try:
        r = httpx.post(f"{settings.query_engine_url}/v1/query/execute", json={
            "sql": sql, "params": params, "question": question, "row_limit": 5000,
        }, headers={
            "X-Tenant-Id": str(tenant_id), "X-User-Id": str(user_id),
        }, timeout=15)
        if r.status_code == 200:
            d = r.json()
            return d.get("rows", []), {
                "mode": "query-engine",
                "cache_hit": d.get("cache_hit", False),
                "exec_ms": d.get("exec_ms", 0),
            }
        log.warning("query-engine %s: %s", r.status_code, r.text[:200])
    except Exception as e:
        log.warning("query-engine unreachable: %s", e)

    # 2) 直连 (兼容旧路径)
    try:
        import pymysql
        jdbc = settings.sr_jdbc_url.replace("jdbc:mysql://", "")
        hp, db = jdbc.split("/", 1)
        host, port = hp.split(":")
        safe = sql
        for k in params: safe = safe.replace(f":{k}", f"%({k})s")
        conn = pymysql.connect(host=host, port=int(port), user=settings.sr_user,
                               password=settings.sr_pass, db=db, charset="utf8mb4",
                               cursorclass=pymysql.cursors.DictCursor, connect_timeout=3)
        try:
            with conn.cursor() as cur:
                cur.execute(safe, params)
                return list(cur.fetchall()), {"mode": "direct"}
        finally:
            conn.close()
    except Exception as e:
        log.warning("direct SQL also failed, returning demo: %s", e)

    # 3) demo 兜底 (degraded=True 让 caller 告知用户)
    return _demo_rows(), {"mode": "demo", "degraded": True}


# 旧名保留(报错时给 schedule executor 留接口)
def _execute_sql(sql: str, params: dict) -> list[dict]:
    rows, _meta = _execute_sql_safe(sql, params, 0, 0, "")
    return rows


def _demo_rows() -> list[dict]:
    return [
        {"biz_date": "2026-05-12", "region": "华东", "sales_amount": 18200000.0, "sales_tonnage": 4820.0},
        {"biz_date": "2026-05-12", "region": "华南", "sales_amount":  8900000.0, "sales_tonnage": 2400.0},
        {"biz_date": "2026-05-12", "region": "华北", "sales_amount":  5600000.0, "sales_tonnage": 1520.0},
    ]


def _tokenize(text: str) -> list[str]:
    """简单按字符切片, 模拟流式效果."""
    out, buf = [], ""
    for c in text:
        buf += c
        if len(buf) >= 6:
            out.append(buf); buf = ""
    if buf: out.append(buf)
    return out


def _drilldown_suggestions(intent, dsl) -> list[dict]:
    suggestions = []
    dims = dsl.get("dimensions") or []
    if "customer" not in dims:
        suggestions.append({
            "label": "按客户拆解",
            "dsl": {**dsl, "dimensions": [*dims, "customer"], "limit": 10},
        })
    if "material.product_type" not in dims:
        suggestions.append({
            "label": "按产品类型拆解",
            "dsl": {**dsl, "dimensions": [*dims, "material.product_type"]},
        })
    if not dsl.get("compare"):
        suggestions.append({
            "label": "对比上周",
            "dsl": {**dsl, "compare": {"mode": "wow"}},
        })
    return suggestions[:3]
