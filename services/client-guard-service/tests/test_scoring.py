from datetime import datetime, timedelta, timezone

from client_guard import scoring
from client_guard.models import GuardEvent, GuardPolicy

P = GuardPolicy()
NOW = datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc)   # 北京时间 10:00


def test_score_ignores_client_weight_and_caps():
    sigs = [("InjectedInput", NOW, 999.0)] * 50           # 客户端声称权重 999,不可信
    score, bd = scoring.score_signals(P, sigs, NOW)
    assert score == 40 and bd["InjectedInput"] == 40      # 3 × 50 = 150 → cap 40


def test_decay():
    sigs = [("RoboticTiming", NOW - timedelta(seconds=300), None)]
    score, _ = scoring.score_signals(P, sigs, NOW)
    assert abs(score - 10) < 0.01


def test_levels():
    assert scoring.level_of(P, 10) == "Low"
    assert scoring.level_of(P, 30) == "Elevated"
    assert scoring.level_of(P, 60) == "High"
    assert scoring.level_of(P, 85) == "Critical"


def _ev(**kw):
    base = dict(event_id="x", tenant_id=1, user_id=1, at=NOW, type="signal")
    base.update(kw)
    return GuardEvent(**base)


def test_multi_device_concurrent():
    evs = [_ev(event_id="a", device_id="dev-A"), _ev(event_id="b", device_id="dev-B")]
    sigs = scoring.server_only_signals(P, evs, NOW, 0, 0)
    assert ("MultiDeviceConcurrent", NOW, None) in sigs


def test_off_hours_bulk_export():
    night = datetime(2026, 9, 7, 18, 30, tzinfo=timezone.utc)   # 北京 02:30
    evs = [_ev(event_id=str(i), type="export", at=night + timedelta(minutes=i)) for i in range(3)]
    sigs = scoring.server_only_signals(P, evs, night + timedelta(hours=1), 0, 0)
    assert any(k == "OffHoursBulk" for k, _, _ in sigs)


def test_server_quota_signal():
    sigs = scoring.server_only_signals(P, [], NOW, exports_last_hour=11, rows_today=0)
    assert any(k == "ServerExportQuota" for k, _, _ in sigs)
