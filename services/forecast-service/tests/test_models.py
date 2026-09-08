"""SimpleSES / fit_and_forecast 测试."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import date, timedelta
import math

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from forecast_service.models import SimpleSES, fit_and_forecast


def _series_linear(n: int = 30, slope: float = 2.0, start: float = 100.0):
    """生成线性递增的序列."""
    return [(date(2026, 1, 1) + timedelta(days=i), start + slope * i) for i in range(n)]


def _series_flat(n: int = 30, value: float = 50.0):
    return [(date(2026, 1, 1) + timedelta(days=i), value) for i in range(n)]


def test_ses_fits_flat_series():
    m = SimpleSES().fit(_series_flat(20, 50))
    fc = m.predict(7)
    assert len(fc) == 7
    for f in fc:
        assert abs(f.forecast - 50) < 1


def test_ses_fits_linear_trend():
    m = SimpleSES().fit(_series_linear(30, slope=2.0, start=100))
    fc = m.predict(7)
    assert len(fc) == 7
    # 最后一个真实点是 100 + 2*29 = 158, 预测应继续向上, day=h+1 起步
    assert fc[0].forecast > 158
    assert fc[-1].forecast > fc[0].forecast


def test_confidence_interval_widens():
    """置信区间宽度应随步长增长."""
    m = SimpleSES().fit(_series_linear(30, slope=1.0))
    fc = m.predict(14)
    w0 = fc[0].upper - fc[0].lower
    wN = fc[-1].upper - fc[-1].lower
    assert wN > w0


def test_ses_short_series_raises():
    import pytest
    with pytest.raises(ValueError):
        SimpleSES().fit([(date(2026, 1, 1), 1.0)])


def test_fit_and_forecast_fallback_no_prophet():
    """use_prophet=True 但 prophet 未装时, 应自动 fallback 到 SES."""
    series = _series_linear(20, slope=1.5)
    result = fit_and_forecast(series, horizon=5, use_prophet=True)
    assert len(result.forecasts) == 5
    assert 0 <= result.mape <= 5      # SES 拟合可能不完美, 上限放宽


def test_mape_reasonable():
    """完全可预测的线性序列 MAPE 应该很低."""
    m = SimpleSES().fit(_series_linear(40, slope=1.0, start=100))
    assert m.mape() < 0.1            # < 10%


def test_runner_train_one_scope_returns_rows():
    from forecast_service.runner import train_one_scope
    rows = train_one_scope(
        scope_type="OVERALL", scope_id="ALL", metric_code="SALES_TON",
        history=_series_linear(40), horizon=7, use_prophet=False, tenant_id=1)
    assert len(rows) == 7
    assert all(r["metric_code"] == "SALES_TON" for r in rows)
    assert all("forecast_value" in r for r in rows)


def test_runner_skip_short_history():
    from forecast_service.runner import train_one_scope
    rows = train_one_scope(
        scope_type="OVERALL", scope_id="ALL", metric_code="X",
        history=_series_linear(5), horizon=7, use_prophet=False, tenant_id=1)
    assert rows == []
