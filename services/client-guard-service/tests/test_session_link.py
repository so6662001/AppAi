"""双端绑定(自研 RDP 启动器 ↔ 远程会话 ERP)与合并评分测试."""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta, timezone

os.environ["GUARD_APPROVAL_SECRET"] = "test-secret"
os.environ.pop("DB_URL_GOV", None)

from fastapi.testclient import TestClient  # noqa: E402
from client_guard import app as appmod, scoring  # noqa: E402
from client_guard.models import GuardEvent, GuardPolicy  # noqa: E402
from client_guard.store import MemoryStore  # noqa: E402

client = TestClient(appmod.app)
T, U = 1001, 7
LAUNCHER_DEV, REMOTE_DEV = "launcher-aaaa", "rds-bbbb"


def _reset():
    appmod.store = MemoryStore()


def _ev(side, device, kind="RemoteSession", link_id=None, client_name=None, type_="signal", at=None):
    return {"event_id": uuid.uuid4().hex, "tenant_id": T, "user_id": U, "device_id": device, "session_id": "s",
            "side": side, "link_id": link_id, "client_name": client_name,
            "at": (at or datetime.now(timezone.utc)).isoformat(), "type": type_, "kind": kind, "weight": 1, "score": 0, "level": "Low"}


def _launch(score=0.0):
    return client.post("/v1/session/launch", json={"tenant_id": T, "user_id": U, "device_id": LAUNCHER_DEV,
                                                   "machine_name": "PC-ZHANGSAN", "local_score": score, "local_level": "Low"}).json()


def test_launch_and_bind_by_ticket():
    _reset()
    l = _launch()
    assert l["connect_advice"] == "allow" and l["ticket"] and l["link_id"]

    b = client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": l["ticket"], "client_name": "PC-ZHANGSAN",
                                              "client_address": "10.0.0.8", "remote_device_id": REMOTE_DEV}).json()
    assert b["linked"] is True and b["matched_by"] == "ticket"
    assert b["link_id"] == l["link_id"] and b["device_id"] == LAUNCHER_DEV   # 远程端沿用启动器指纹

    info = client.get(f"/v1/session/{l['link_id']}").json()
    assert info["status"] == "bound" and info["client_address"] == "10.0.0.8" and "ticket_nonce" not in info

    # 同一票据被另一台远程设备重放 → 拒绝
    b2 = client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": l["ticket"], "remote_device_id": "other"}).json()
    assert b2["linked"] is False


def test_bind_rejects_tampered_ticket_and_wrong_user():
    _reset()
    l = _launch()
    bad = l["ticket"][:-3] + "abc"
    assert client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": bad, "remote_device_id": REMOTE_DEV}).json()["linked"] is False
    assert client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U + 1, "ticket": l["ticket"], "remote_device_id": REMOTE_DEV}).json()["linked"] is False


def test_bind_fallback_by_client_name():
    _reset()
    _launch()
    # ERP 没拿到票据(老启动器没传 StartProgram 参数),用 WTSClientName 兜底
    b = client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "client_name": "pc-zhangsan", "remote_device_id": REMOTE_DEV}).json()
    assert b["linked"] is True and b["matched_by"] == "client_name" and b["device_id"] == LAUNCHER_DEV
    # 完全无关的客户机名 → 未配对
    b2 = client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "client_name": "HACKER-PC", "remote_device_id": "x"}).json()
    assert b2["linked"] is False


def test_launch_advice_follows_risk():
    _reset()
    assert _launch(score=45)["connect_advice"] == "clipboard_off"
    assert _launch(score=70)["connect_advice"] == "deny"
    # 服务端历史风险也会计入:远程端先上报一个 RPA 进程 → 再申请票据被拒
    _reset()
    client.post("/v1/events", json=[_ev("remote", REMOTE_DEV, kind="KnownAutomationProcess"), _ev("remote", REMOTE_DEV, kind="UiaProbing")])
    assert _launch(score=0)["connect_advice"] == "deny"


def test_launcher_plus_bound_remote_is_one_device():
    """一台 PC 通过启动器登录 RDS:启动器 + 远程会话两路事件不能被判成"多设备并发"."""
    _reset()
    l = _launch()
    client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": l["ticket"], "client_name": "PC-ZHANGSAN", "remote_device_id": REMOTE_DEV})
    evs = [
        _ev("launcher", LAUNCHER_DEV, kind="VirtualMachine", link_id=l["link_id"], client_name="PC-ZHANGSAN"),
        _ev("remote", REMOTE_DEV, kind="RemoteSession", link_id=l["link_id"], client_name="PC-ZHANGSAN"),   # 绑定前发出的
        _ev("remote", LAUNCHER_DEV, kind="RemoteSession", link_id=l["link_id"], client_name="PC-ZHANGSAN"),  # 绑定后沿用启动器指纹
    ]
    client.post("/v1/events", json=evs)
    risk = client.get(f"/v1/risk/{T}/{U}").json()
    assert "MultiDeviceConcurrent" not in risk["breakdown"]

    # 真正的第二台设备出现 → 命中
    client.post("/v1/events", json=[_ev("local", "laptop-cccc", kind="VirtualMachine")])
    risk = client.get(f"/v1/risk/{T}/{U}").json()
    assert "MultiDeviceConcurrent" in risk["breakdown"]


def test_concurrent_devices_unpaired_remote_grouped_by_client_name():
    now = datetime.now(timezone.utc)
    evs = [GuardEvent(event_id=uuid.uuid4().hex, tenant_id=T, user_id=U, device_id=d, side="remote", client_name=cn, at=now)
           for d, cn in [("rds-1", "PC-A"), ("rds-1", "PC-A"), ("rds-2", "PC-A")]]
    assert scoring.concurrent_devices(evs) == {"client:pc-a"}
    evs.append(GuardEvent(event_id=uuid.uuid4().hex, tenant_id=T, user_id=U, device_id="rds-3", side="remote", client_name="PC-B", at=now))
    assert len(scoring.concurrent_devices(evs)) == 2


def test_unpaired_remote_export_requires_approval_or_denied():
    _reset()
    # 用 mstsc 直连的远程会话(没有 launcher 事件、没有 link),小额导出也要审批
    client.post("/v1/events", json=[_ev("remote", REMOTE_DEV, client_name="HACKER-PC")])
    r = client.post("/v1/export/request", json={"tenant_id": T, "user_id": U, "data_set": "sales", "row_count": 100,
                                                "device_id": REMOTE_DEV, "risk_score": 0, "reason": ""}).json()
    assert r["status"] == "pending" and "登录器" in r["message"]

    # 策略改为 deny
    p = GuardPolicy()
    p.rdp.unpaired_remote_export = "deny"
    client.put(f"/v1/policy/{T}", json=p.model_dump(mode="json"))
    r = client.post("/v1/export/request", json={"tenant_id": T, "user_id": U, "data_set": "sales", "row_count": 100,
                                                "device_id": REMOTE_DEV, "risk_score": 0, "reason": ""}).json()
    assert r["status"] == "denied"


def test_paired_remote_export_auto_approved():
    _reset()
    l = _launch()
    client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": l["ticket"], "client_name": "PC-ZHANGSAN", "remote_device_id": REMOTE_DEV})
    client.post("/v1/events", json=[_ev("launcher", LAUNCHER_DEV, kind="VirtualMachine", link_id=l["link_id"], client_name="PC-ZHANGSAN"),
                                    _ev("remote", LAUNCHER_DEV, link_id=l["link_id"], client_name="PC-ZHANGSAN")])
    r = client.post("/v1/export/request", json={"tenant_id": T, "user_id": U, "data_set": "sales", "row_count": 100,
                                                "device_id": LAUNCHER_DEV, "risk_score": 0, "reason": ""}).json()
    assert r["status"] == "approved" and r["approver"] == "auto"


def test_policy_roundtrip_includes_rdp_section():
    _reset()
    p = client.get("/v1/policy", params={"tenant_id": 1}).json()
    assert p["rdp"]["redirect_clipboard"] is False and p["rdp"]["redirect_drives"] is False
    assert p["rdp"]["start_program_only"] is True and p["rdp"]["launcher_exclude_from_capture"] is True


def test_ticket_expires():
    _reset()
    p = GuardPolicy()
    p.rdp.ticket_ttl_sec = -10   # 立即过期
    client.put(f"/v1/policy/{T}", json=p.model_dump(mode="json"))
    l = _launch()
    b = client.post("/v1/session/bind", json={"tenant_id": T, "user_id": U, "ticket": l["ticket"], "remote_device_id": REMOTE_DEV}).json()
    assert b["linked"] is False and "expired" in b["message"]
