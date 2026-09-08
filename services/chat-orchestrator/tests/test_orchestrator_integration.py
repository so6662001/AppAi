"""orchestrator.stream 集成测试 + billing_client outbox 测试.

不依赖真实 DB / Redis / billing-service, 全部 mock.
"""
from __future__ import annotations
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _drain(agen):
    """收集 async generator 所有事件."""
    out = []
    async def _run():
        async for ev in agen:
            out.append(ev)
    asyncio.run(_run())
    return out


def test_stream_emits_warning_when_data_unavailable(monkeypatch):
    """SQL 不可达时, stream 应明确发 warning 事件而非静默."""
    from chat_orchestrator import orchestrator

    # mock dsl-compiler 返回成功
    fake_compiled = MagicMock(); fake_compiled.status_code = 200
    fake_compiled.json.return_value = {
        "sql": "SELECT 1", "params": {},
        "tables_used": ["dws_sales_daily"],
        "metrics_expanded": ["sales_amount"],
        "biz_token_estimate": 200,
    }
    monkeypatch.setattr("httpx.AsyncClient.post",
                        lambda self, *a, **k: _async_resp(fake_compiled))
    # mock 真实查询失败 → 触发 degraded
    monkeypatch.setattr(orchestrator, "_execute_sql_safe",
                        lambda *a, **k: (orchestrator._demo_rows(),
                                          {"mode": "demo", "degraded": True}))
    # mock session_db 与 billing 不写库
    monkeypatch.setattr(orchestrator.session_db, "ensure_session",
                        lambda *a, **k: "sid")
    monkeypatch.setattr(orchestrator.session_db, "save_user_message",
                        lambda *a, **k: "umid")
    monkeypatch.setattr(orchestrator.session_db, "save_assistant_message",
                        lambda **kw: None)
    monkeypatch.setattr(orchestrator.billing_client, "preauth",
                        lambda *a, **k: None)
    monkeypatch.setattr(orchestrator.billing_client, "settle",
                        lambda *a, **k: True)

    events = _drain(orchestrator.stream(
        text="昨天销售额", tenant_id=1, user_id=1, business_line="TRADE"))
    types = [e["event"] for e in events]
    assert "warning" in types, f"degraded query 应有 warning 事件, 实际 {types}"
    warn = next(e for e in events if e["event"] == "warning")
    assert warn["data"]["code"] == "W_DATA_UNAVAILABLE"


def _async_resp(resp_mock):
    """httpx.AsyncClient.post 的 async wrapper."""
    async def _coro():
        return resp_mock
    return _coro()


def test_billing_outbox_writes_on_failure(tmp_path, monkeypatch):
    """billing-service 不可达时, settle 失败应写入 outbox."""
    monkeypatch.setenv("BILLING_OUTBOX_DIR", str(tmp_path))
    # reload module
    import importlib
    from chat_orchestrator import billing_client
    importlib.reload(billing_client)

    # mock httpx 抛异常
    monkeypatch.setattr("httpx.post", lambda *a, **k:
                        (_ for _ in ()).throw(ConnectionError("down")))

    ok = billing_client.settle(tenant_id=1, reservation_id="abc", actual=100,
                                model_name="m", input_tokens=10, output_tokens=10,
                                query_rows=0, cache_hit=False)
    assert ok is False
    # outbox 应有 1 个文件
    files = list(Path(tmp_path).glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["kind"] == "settle"
    assert data["payload"]["reservation_id"] == "abc"


def test_billing_preauth_no_outbox_on_402(tmp_path, monkeypatch):
    """402 (余额不足) 是业务错误, 不应进 outbox 重试."""
    monkeypatch.setenv("BILLING_OUTBOX_DIR", str(tmp_path))
    import importlib
    from chat_orchestrator import billing_client
    importlib.reload(billing_client)

    resp = MagicMock(); resp.status_code = 402
    monkeypatch.setattr("httpx.post", lambda *a, **k: resp)

    rid = billing_client.preauth(tenant_id=1, user_id=1,
                                  session_id="s", message_id="m", estimate=100)
    assert rid is None
    files = list(Path(tmp_path).glob("*.json"))
    assert len(files) == 0
