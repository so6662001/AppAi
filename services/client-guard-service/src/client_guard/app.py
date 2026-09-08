"""FastAPI 入口 - client-guard-service (端口 8980).

职责(客户端 SDK 不可信,这里是最后一道门):
  GET  /v1/policy                       策略下发(租户覆盖 + 默认)
  PUT  /v1/policy/{tenant_id}           管理员更新策略
  POST /v1/events                       批量遥测 → 服务端独立评分 → 下发 directive
  POST /v1/export/request               导出申请(服务端配额 + 自动 / 人工审批)
  GET  /v1/export/request/{id}          轮询审批状态
  POST /v1/export/request/{id}/decide   审批人决定
  GET  /v1/export/requests              审批列表(registry-web 用)
  GET  /v1/export/verify                业务后端 / 客户端校验 token
  POST /v1/export/consume               业务后端真正导出前:校验 + 一次性消费 + 记账
  GET  /v1/risk/{tenant_id}/{user_id}   当前服务端评分
  PUT  /v1/devices/{tenant_id}/{user_id}/{device_id}/directive   人工锁定 / 解锁 / 标记可信
"""
from __future__ import annotations
import logging
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from . import approval, scoring
from .models import (ApproveIn, DeviceDirectiveIn, ExportRequestIn, ExportRequestOut, ExportRequestRecord,
                     GuardEvent, GuardPolicy, TelemetryResponse)
from .store import MemoryStore, MySqlStore, Store

log = logging.getLogger("client-guard")
app = FastAPI(title="client-guard-service", version="0.1.0")

SECRET = os.environ.get("GUARD_APPROVAL_SECRET", "change-me-guard-secret")
DB_URL = os.environ.get("DB_URL_GOV")
store: Store = MySqlStore(DB_URL) if DB_URL else MemoryStore()

try:
    sys.path.append(os.environ.get("SHARED_PATH", "/opt/shared"))
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../_shared")))
    import observability  # type: ignore
    observability.setup(app, service_name="client-guard-service")
except Exception:  # noqa: BLE001
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _policy(tenant_id: int) -> GuardPolicy:
    return store.get_policy(tenant_id) or store.get_policy(0) or GuardPolicy()


@app.get("/healthz")
def healthz():
    return {"ok": True, "store": type(store).__name__}


# ----------------------------------------------------------------- 策略
@app.get("/v1/policy", response_model=GuardPolicy)
def get_policy(tenant_id: int = Query(...)):
    return _policy(tenant_id)


@app.put("/v1/policy/{tenant_id}", response_model=GuardPolicy)
def put_policy(tenant_id: int, policy: GuardPolicy, updated_by: Optional[int] = None):
    old = store.get_policy(tenant_id)
    policy.version = (old.version + 1) if old else max(1, policy.version)
    store.put_policy(tenant_id, policy, updated_by)
    return policy


# ----------------------------------------------------------------- 遥测
def _server_score(tenant_id: int, user_id: int, now: datetime) -> tuple[float, dict[str, float], str]:
    policy = _policy(tenant_id)
    events = store.recent_events(tenant_id, user_id, now - timedelta(hours=12))
    sigs: list[tuple[str, datetime, float | None]] = [
        (e.kind, e.at, e.weight) for e in events if e.type == "signal" and e.kind]
    hour, day = store.export_usage(tenant_id, user_id, now)
    sigs += scoring.server_only_signals(policy, events, now, hour, day)
    score, breakdown = scoring.score_signals(policy, sigs, now)
    return score, breakdown, scoring.level_of(policy, score)


@app.post("/v1/events", response_model=TelemetryResponse)
def post_events(events: list[GuardEvent]):
    if not events:
        return TelemetryResponse(accepted=0)
    accepted = store.add_events(events)
    now = _now()
    e0 = events[-1]
    score, _, level = _server_score(e0.tenant_id, e0.user_id, now)
    store.touch_device(e0.tenant_id, e0.user_id, e0.device_id, score, now)

    directive, reason = store.get_directive(e0.tenant_id, e0.user_id, e0.device_id, now)
    if directive == "none" and not store.is_trusted(e0.tenant_id, e0.user_id, e0.device_id):
        if level == "Critical":
            directive, reason = "lock", f"服务端评分 {score:.0f} 达到临界"
            store.set_directive(e0.tenant_id, e0.user_id, e0.device_id, "lock", reason, now + timedelta(minutes=30), None)
        elif level == "High":
            directive, reason = "degrade", f"服务端评分 {score:.0f} 偏高"
    policy = _policy(e0.tenant_id)
    return TelemetryResponse(accepted=accepted, directive=directive, message=reason or None,
                             policy_version=policy.version, server_score=round(score, 1))


@app.get("/v1/risk/{tenant_id}/{user_id}")
def get_risk(tenant_id: int, user_id: int):
    score, breakdown, level = _server_score(tenant_id, user_id, _now())
    hour, day = store.export_usage(tenant_id, user_id, _now())
    return {"tenant_id": tenant_id, "user_id": user_id, "score": round(score, 1), "level": level,
            "breakdown": {k: round(v, 1) for k, v in breakdown.items()}, "exports_last_hour": hour, "rows_today": day}


# ----------------------------------------------------------------- 导出申请 / 审批
def _issue_for(r: ExportRequestRecord, approver: str, max_rows: int, ttl_minutes: int) -> None:
    exp = int(_now().timestamp()) + ttl_minutes * 60
    r.token = approval.issue(SECRET, r.tenant_id, r.user_id, r.data_set, max_rows, exp, approver)
    r.token_expires_at = exp
    r.status = "approved"
    r.approver_name = approver
    r.decided_at = _now()


@app.post("/v1/export/request", response_model=ExportRequestOut)
def request_export(req: ExportRequestIn):
    now = _now()
    policy = _policy(req.tenant_id)
    q = policy.export_quota
    rec = ExportRequestRecord(request_id=secrets.token_hex(16), tenant_id=req.tenant_id, user_id=req.user_id,
                              device_id=req.device_id, data_set=req.data_set, row_count=req.row_count,
                              risk_score=req.risk_score, reason=req.reason, created_at=now)

    directive, dreason = store.get_directive(req.tenant_id, req.user_id, req.device_id, now)
    if directive == "lock":
        rec.status, rec.approve_note = "denied", "device locked: " + dreason
        store.put_request(rec)
        return ExportRequestOut(status="denied", request_id=rec.request_id, message="该设备已被锁定:" + dreason)

    hour, day = store.export_usage(req.tenant_id, req.user_id, now)
    if hour >= q.max_exports_per_hour:
        rec.status, rec.approve_note = "denied", "quota exports/hour"
        store.put_request(rec)
        return ExportRequestOut(status="denied", request_id=rec.request_id, message=f"1 小时内导出次数已达 {q.max_exports_per_hour} 次")
    if day + req.row_count > q.max_rows_per_day:
        rec.status, rec.approve_note = "denied", "quota rows/day"
        store.put_request(rec)
        return ExportRequestOut(status="denied", request_id=rec.request_id, message=f"今日导出行数将超过 {q.max_rows_per_day:,} 行")
    if req.row_count > q.max_rows_per_export * 4:
        rec.status, rec.approve_note = "denied", "row_count too large"
        store.put_request(rec)
        return ExportRequestOut(status="denied", request_id=rec.request_id, message=f"单次最多 {q.max_rows_per_export * 4:,} 行,请分批")

    server_score, _, level = _server_score(req.tenant_id, req.user_id, now)
    rec.risk_score = max(req.risk_score, server_score)
    trusted = store.is_trusted(req.tenant_id, req.user_id, req.device_id)

    # 自动放行:风险低 且 (行数在阈值内 或 可信设备)
    if level == "Low" and (req.row_count <= q.approval_threshold_rows or trusted):
        _issue_for(rec, "auto", max(req.row_count, q.approval_threshold_rows), 30)
        store.put_request(rec)
        return ExportRequestOut(status="approved", request_id=rec.request_id, token=rec.token, approver="auto",
                                message="自动放行")

    # 其余进入人工审批
    rec.status = "pending"
    store.put_request(rec)
    return ExportRequestOut(status="pending", request_id=rec.request_id,
                            message=f"已提交审批(风险 {level} / {req.row_count} 行),请等待主管处理")


@app.get("/v1/export/request/{request_id}", response_model=ExportRequestOut)
def poll_export(request_id: str):
    r = store.get_request(request_id)
    if not r:
        raise HTTPException(404, "request not found")
    return ExportRequestOut(status=r.status if r.status != "used" else "approved", request_id=r.request_id,
                            token=r.token if r.status == "approved" else None, approver=r.approver_name, message=r.approve_note)


@app.post("/v1/export/request/{request_id}/decide", response_model=ExportRequestOut)
def decide_export(request_id: str, body: ApproveIn):
    r = store.get_request(request_id)
    if not r:
        raise HTTPException(404, "request not found")
    if r.status != "pending":
        raise HTTPException(409, f"request already {r.status}")
    if body.approver_id == r.user_id:
        raise HTTPException(403, "不能审批自己的导出申请")
    r.approver_id, r.approve_note = body.approver_id, body.note
    if body.approve:
        _issue_for(r, body.approver_name, body.max_rows or r.row_count, body.ttl_minutes)
    else:
        r.status, r.approver_name, r.decided_at = "denied", body.approver_name, _now()
    store.put_request(r)
    return ExportRequestOut(status=r.status, request_id=r.request_id, token=r.token, approver=r.approver_name, message=r.approve_note)


@app.get("/v1/export/requests")
def list_exports(tenant_id: int, status: Optional[str] = None, limit: int = 100):
    return [r.model_dump(mode="json", exclude={"token"}) for r in store.list_requests(tenant_id, status, limit)]


@app.get("/v1/export/verify")
def verify_token(token: str, data_set: Optional[str] = None, row_count: Optional[int] = None,
                 tenant_id: Optional[int] = None, user_id: Optional[int] = None):
    r = approval.verify(SECRET, token, tenant_id=tenant_id, user_id=user_id, data_set=data_set, row_count=row_count)
    return {"valid": r.valid, "error": r.error or None, "approver": r.approver, "max_rows": r.max_rows,
            "expires_at": r.expires_at, "tenant_id": r.tenant_id, "user_id": r.user_id}


@app.post("/v1/export/consume")
def consume_token(token: str, data_set: str, row_count: int, tenant_id: int, user_id: int):
    """业务后端(Java / ERP)在生成 Excel 前调用:校验 + 一次性消费 + 记入服务端配额账本."""
    r = approval.verify(SECRET, token, tenant_id=tenant_id, user_id=user_id, data_set=data_set, row_count=row_count)
    if not r.valid:
        raise HTTPException(403, f"invalid token: {r.error}")
    if not store.mark_token_used(r.nonce):
        raise HTTPException(409, "token already used")
    store.record_export(tenant_id, user_id, row_count, _now())
    return {"ok": True, "approver": r.approver, "max_rows": r.max_rows}


@app.post("/v1/export/record")
def record_export(tenant_id: int, user_id: int, row_count: int):
    """小额导出(未走审批 token)完成后由业务后端记账,保证服务端配额准确."""
    store.record_export(tenant_id, user_id, row_count, _now())
    hour, day = store.export_usage(tenant_id, user_id, _now())
    return {"ok": True, "exports_last_hour": hour, "rows_today": day}


# ----------------------------------------------------------------- 设备指令
@app.put("/v1/devices/{tenant_id}/{user_id}/{device_id}/directive")
def set_directive(tenant_id: int, user_id: int, device_id: str, body: DeviceDirectiveIn):
    if body.directive not in ("none", "degrade", "lock"):
        raise HTTPException(400, "directive must be none/degrade/lock")
    until = _now() + timedelta(minutes=body.minutes) if body.directive != "none" else None
    store.set_directive(tenant_id, user_id, device_id, body.directive, body.reason, until, body.trusted)
    return {"ok": True, "directive": body.directive, "until": until.isoformat() if until else None}
