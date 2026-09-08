"""HTTP API 测试(MemoryStore)."""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timezone

os.environ["GUARD_APPROVAL_SECRET"] = "test-secret"
os.environ.pop("DB_URL_GOV", None)

from fastapi.testclient import TestClient  # noqa: E402
from client_guard import app as appmod      # noqa: E402
from client_guard.store import MemoryStore  # noqa: E402

client = TestClient(appmod.app)


def _reset():
    appmod.store = MemoryStore()


def _event(tenant=1001, user=1023, device="dev-1", kind="KnownAutomationProcess", type_="signal", **kw):
    e = {"event_id": uuid.uuid4().hex, "tenant_id": tenant, "user_id": user, "device_id": device, "session_id": "s1",
         "at": datetime.now(timezone.utc).isoformat(), "type": type_, "kind": kind, "weight": 40, "score": 40,
         "level": "Elevated", "detail": "uirobot"}
    e.update(kw)
    return e


def test_healthz():
    assert client.get("/healthz").json()["ok"] is True


def test_policy_default_and_override():
    _reset()
    r = client.get("/v1/policy", params={"tenant_id": 5}).json()
    assert r["thresholds"]["critical"] == 85 and r["export_quota"]["max_rows_per_export"] == 20000

    r2 = client.put("/v1/policy/5", json={**r, "export_quota": {**r["export_quota"], "max_rows_per_export": 500}}).json()
    assert r2["version"] == 1 and r2["export_quota"]["max_rows_per_export"] == 500
    r3 = client.put("/v1/policy/5", json=r2).json()
    assert r3["version"] == 2
    assert client.get("/v1/policy", params={"tenant_id": 5}).json()["export_quota"]["max_rows_per_export"] == 500
    assert client.get("/v1/policy", params={"tenant_id": 6}).json()["export_quota"]["max_rows_per_export"] == 20000


def test_events_scoring_and_lock_directive():
    _reset()
    # 一个 RPA 进程 → Elevated,无指令
    r = client.post("/v1/events", json=[_event()]).json()
    assert r["accepted"] == 1 and r["directive"] == "none" and 39 < r["server_score"] < 41

    # 再加 UIA 探测 + 机器节律 + 调试器 → 40+25+20+30 → Critical → lock
    r = client.post("/v1/events", json=[_event(kind="UiaProbing"), _event(kind="RoboticTiming"), _event(kind="DebuggerAttached")]).json()
    assert r["server_score"] >= 85 and r["directive"] == "lock"

    # 重复 event_id 幂等
    e = _event(kind="TeleportClick")
    assert client.post("/v1/events", json=[e]).json()["accepted"] == 1
    assert client.post("/v1/events", json=[e]).json()["accepted"] == 0

    risk = client.get("/v1/risk/1001/1023").json()
    assert risk["level"] == "Critical" and "KnownAutomationProcess" in risk["breakdown"]

    # 锁定后导出被拒
    r = client.post("/v1/export/request", json={"tenant_id": 1001, "user_id": 1023, "data_set": "so", "row_count": 10, "device_id": "dev-1"}).json()
    assert r["status"] == "denied" and "锁定" in r["message"]

    # 管理员解锁 + 标记可信
    client.put("/v1/devices/1001/1023/dev-1/directive", json={"directive": "none", "trusted": True})
    r = client.post("/v1/events", json=[_event(kind="TeleportClick")]).json()
    assert r["directive"] == "none"   # 可信设备不再自动下发


def test_export_auto_approve_verify_consume():
    _reset()
    body = {"tenant_id": 1001, "user_id": 2000, "data_set": "sales_order", "row_count": 1200, "device_id": "d"}
    r = client.post("/v1/export/request", json=body).json()
    assert r["status"] == "approved" and r["token"] and r["approver"] == "auto"

    v = client.get("/v1/export/verify", params={"token": r["token"], "data_set": "sales_order", "row_count": 1200}).json()
    assert v["valid"] is True and v["max_rows"] >= 1200

    bad = client.get("/v1/export/verify", params={"token": r["token"], "data_set": "sales_order", "row_count": 999999}).json()
    assert bad["valid"] is False and bad["error"] == "rows"

    # 业务后端消费:一次性
    c = client.post("/v1/export/consume", params={"token": r["token"], "data_set": "sales_order", "row_count": 1200, "tenant_id": 1001, "user_id": 2000})
    assert c.status_code == 200
    c2 = client.post("/v1/export/consume", params={"token": r["token"], "data_set": "sales_order", "row_count": 1200, "tenant_id": 1001, "user_id": 2000})
    assert c2.status_code == 409

    risk = client.get("/v1/risk/1001/2000").json()
    assert risk["exports_last_hour"] == 1 and risk["rows_today"] == 1200


def test_export_pending_then_manual_decide():
    _reset()
    body = {"tenant_id": 1001, "user_id": 3000, "data_set": "sales_order", "row_count": 8000, "device_id": "d"}
    r = client.post("/v1/export/request", json=body).json()
    assert r["status"] == "pending"
    rid = r["request_id"]

    assert client.get(f"/v1/export/request/{rid}").json()["status"] == "pending"
    lst = client.get("/v1/export/requests", params={"tenant_id": 1001, "status": "pending"}).json()
    assert len(lst) == 1 and "token" not in lst[0]

    # 不能自己审批
    assert client.post(f"/v1/export/request/{rid}/decide", json={"approver_id": 3000, "approver_name": "self"}).status_code == 403

    d = client.post(f"/v1/export/request/{rid}/decide", json={"approver_id": 1, "approver_name": "李经理", "note": "ok", "max_rows": 8000}).json()
    assert d["status"] == "approved" and d["token"]
    p = client.get(f"/v1/export/request/{rid}").json()
    assert p["status"] == "approved" and p["token"] == d["token"] and p["approver"] == "李经理"

    # 重复审批 409
    assert client.post(f"/v1/export/request/{rid}/decide", json={"approver_id": 1, "approver_name": "李经理"}).status_code == 409


def test_export_denied_by_risk_goes_pending_and_quota_denies():
    _reset()
    client.post("/v1/events", json=[_event(user=4000, kind="KnownAutomationProcess"), _event(user=4000, kind="UiaProbing")])
    r = client.post("/v1/export/request", json={"tenant_id": 1001, "user_id": 4000, "data_set": "so", "row_count": 10, "device_id": "dev-1"}).json()
    assert r["status"] == "pending"   # High 风险,小批量也要人工

    # 配额:每小时 10 次
    for i in range(10):
        client.post("/v1/export/record", params={"tenant_id": 1001, "user_id": 5000, "row_count": 10})
    # export_usage 的"每小时次数"在 MemoryStore 按 record 计
    r = client.post("/v1/export/request", json={"tenant_id": 1001, "user_id": 5000, "data_set": "so", "row_count": 10, "device_id": "d"}).json()
    assert r["status"] == "denied" and "次数" in r["message"]

    # 单次过大
    r = client.post("/v1/export/request", json={"tenant_id": 1001, "user_id": 6000, "data_set": "so", "row_count": 200000, "device_id": "d"}).json()
    assert r["status"] == "denied" and "分批" in r["message"]
