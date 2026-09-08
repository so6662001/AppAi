"""report-scheduler executor 测试."""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from report_scheduler import executor


def test_exec_via_chat_parses_events(monkeypatch):
    """_exec_via_chat 应正确解析 SSE events 转 blocks/summary/biz_tokens."""
    # 启用 chat 路径
    monkeypatch.setattr(executor, "CHAT_ORCHESTRATOR_URL", "http://chat:8200")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"events": [
        {"event": "status", "data": {"phase": "parsing"}},
        {"event": "data",   "data": {"type": "kpi", "kpis": [{"label": "销售", "value": 100}]}},
        {"event": "token",  "data": "上周"},
        {"event": "token",  "data": "销售 100 元"},
        {"event": "usage",  "data": {"bizTokensCharged": 1800, "queryRows": 5}},
        {"event": "done",   "data": {}},
    ]}
    fake_resp.raise_for_status = lambda: None
    monkeypatch.setattr("httpx.post", lambda *a, **k: fake_resp)

    result = executor._exec_via_chat(
        {"report_id": 1, "dsl_json": {}, "question": "上周销售额", "name": "test"},
        tenant_id=1, user_id=1)
    assert result is not None
    blocks, summary, sql_text, rows, biz_tokens = result
    assert any(b["type"] == "kpi" for b in blocks)
    assert "上周" in summary
    assert "100" in summary
    assert biz_tokens == 1800


def test_exec_via_chat_tolerates_missing_event_fields(monkeypatch):
    """事件缺字段时不应崩溃."""
    monkeypatch.setattr(executor, "CHAT_ORCHESTRATOR_URL", "http://chat:8200")
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {"events": [
        {},                                          # 缺 event 和 data
        {"event": "data"},                           # 缺 data
        {"event": "token", "data": "ok"},
    ]}
    fake_resp.raise_for_status = lambda: None
    monkeypatch.setattr("httpx.post", lambda *a, **k: fake_resp)

    result = executor._exec_via_chat(
        {"report_id": 1, "dsl_json": {}}, 1, 1)
    assert result is not None
    _, summary, _, _, _ = result
    assert "ok" in summary


def test_exec_via_chat_returns_none_on_http_error(monkeypatch):
    """HTTP 失败时返回 None, 触发外层 fallback."""
    monkeypatch.setattr(executor, "CHAT_ORCHESTRATOR_URL", "http://chat:8200")

    def _raise(*a, **k):
        raise ConnectionError("chat down")
    monkeypatch.setattr("httpx.post", _raise)

    result = executor._exec_via_chat({"report_id": 1, "dsl_json": {}}, 1, 1)
    assert result is None
