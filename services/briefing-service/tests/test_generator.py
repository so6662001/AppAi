"""briefing generator 测试 (mock DB)."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import date
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from briefing import generator


def _mock_db_empty_count():
    eng = MagicMock()
    conn = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    # 第 1 次 SELECT COUNT(*) -> 0; 后续 INSERT lastrowid 通过 result.lastrowid 已模拟
    result = MagicMock()
    result.scalar.return_value = 0
    result.mappings.return_value.all.return_value = []
    conn.execute.return_value = result
    return eng


def test_generate_for_user_inserts_summary():
    fake_eng = _mock_db_empty_count()
    inserted = []

    def fake_insert(*args, **kwargs):
        inserted.append({**kwargs, "_args": args})
        return 1
    with patch.object(generator, 'db', return_value=fake_eng), \
         patch.object(generator, 'insert_card', side_effect=fake_insert):
        n = generator.generate_for_user(1, 1, date(2026, 5, 13))
    assert n >= 1
    assert inserted[0]["card_type"] == "SUMMARY"


def test_generate_skips_when_already_generated():
    eng = MagicMock()
    conn = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    result = MagicMock(); result.scalar.return_value = 3   # 已有 3 张
    conn.execute.return_value = result

    inserted = []
    with patch.object(generator, 'db', return_value=eng), \
         patch.object(generator, 'insert_card', side_effect=lambda *a, **k: inserted.append(a) or 1):
        n = generator.generate_for_user(1, 1, date(2026, 5, 13))
    assert n == 0 and inserted == []


def test_generate_all_uses_default_user_when_no_layouts():
    with patch.object(generator, 'all_users', return_value=[]), \
         patch.object(generator, 'generate_for_user', return_value=1) as g:
        n = generator.generate_all(date(2026, 5, 13))
    assert n == 1
    g.assert_called_once_with(1, 1, date(2026, 5, 13))
