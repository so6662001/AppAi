"""tenant_config 缓存逻辑测试 (不依赖真实数据库)。"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from report_scheduler import tenant_config


def _mock_engine(row_value):
    eng = MagicMock()
    conn = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    result = MagicMock()
    result.first.return_value = (row_value,) if row_value is not None else None
    conn.execute.return_value = result
    return eng


def setup_function(_):
    tenant_config.invalidate()


def test_get_config_hits_db_first_time():
    fake = _mock_engine('{"webhook":"https://x.cn/abc"}')
    with patch.object(tenant_config, 'get_engine', return_value=fake):
        cfg = tenant_config.get_config(1, "WECOM")
    assert cfg == {"webhook": "https://x.cn/abc"}


def test_get_config_uses_cache_second_time():
    fake = _mock_engine('{"webhook":"https://x.cn/abc"}')
    with patch.object(tenant_config, 'get_engine', return_value=fake) as m:
        tenant_config.get_config(2, "WECOM")
        tenant_config.get_config(2, "WECOM")        # 第二次应走缓存
    # get_engine 只应被调一次 (第一次)
    assert m.call_count == 1


def test_invalidate_clears():
    fake = _mock_engine('{"x":1}')
    with patch.object(tenant_config, 'get_engine', return_value=fake) as m:
        tenant_config.get_config(3, "DINGTALK")
        tenant_config.invalidate(tenant_id=3)
        tenant_config.get_config(3, "DINGTALK")
    assert m.call_count == 2


def test_missing_config_returns_none():
    fake = _mock_engine(None)
    with patch.object(tenant_config, 'get_engine', return_value=fake):
        cfg = tenant_config.get_config(99, "EMAIL")
    assert cfg is None
