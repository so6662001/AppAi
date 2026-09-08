"""时间序列预测模型 - 两套实现:

1) Prophet (生产推荐) — 由 USE_PROPHET=true 启用
2) SimpleSES (简化指数平滑) — 默认, 零依赖, 易于测试

输入: 时间序列 list[{ds, y}]; 输出: list[{ds, yhat, yhat_lower, yhat_upper}] + mape
"""
from __future__ import annotations
import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable
import statistics


@dataclass
class Forecast:
    target_date: date
    forecast: float
    lower: float
    upper: float


@dataclass
class FitResult:
    forecasts: list[Forecast]
    mape: float                       # 0~1 范围


# ============ SimpleSES: Holt-Winters 阉割版 (level + trend) ============

class SimpleSES:
    def __init__(self, alpha: float = 0.5, beta: float = 0.2, ci_z: float = 1.645):
        self.alpha = alpha     # level
        self.beta = beta       # trend
        self.ci_z = ci_z       # 90% CI
        self.level = None
        self.trend = None
        self.residuals: list[float] = []
        self.last_date: date | None = None

    def fit(self, series: list[tuple[date, float]]) -> "SimpleSES":
        if len(series) < 2:
            raise ValueError("series too short")
        series = sorted(series, key=lambda x: x[0])
        y0 = series[0][1]
        self.level = float(y0)
        self.trend = float(series[1][1] - series[0][1])
        self.residuals = []
        prev_level = self.level
        prev_trend = self.trend
        for d, y in series[1:]:
            forecast = prev_level + prev_trend
            self.residuals.append(float(y) - forecast)
            level = self.alpha * float(y) + (1 - self.alpha) * (prev_level + prev_trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * prev_trend
            prev_level, prev_trend = level, trend
        self.level, self.trend = prev_level, prev_trend
        self.last_date = series[-1][0]
        return self

    def predict(self, horizon: int) -> list[Forecast]:
        if self.level is None or self.last_date is None:
            return []
        sigma = statistics.pstdev(self.residuals) if len(self.residuals) > 1 else 0.0
        # 残差太小或为 0 (完美拟合) 时, 用 level 的 5% 作为最小不确定度
        sigma = max(sigma, abs((self.level or 1) * 0.05))
        out: list[Forecast] = []
        for h in range(1, horizon + 1):
            d = self.last_date + timedelta(days=h)
            y = self.level + self.trend * h
            # 不确定性随步长扩张
            ci = self.ci_z * sigma * math.sqrt(h)
            out.append(Forecast(d, y, y - ci, y + ci))
        return out

    def mape(self) -> float:
        if not self.residuals:
            return 0.0
        # MAPE 近似 = mean(|resid| / |level|)
        denom = abs(self.level) if self.level else 1
        return float(statistics.mean(abs(r) / denom for r in self.residuals))


# ============ Prophet 适配 (可选) ============

def fit_with_prophet(series: list[tuple[date, float]], horizon: int):
    """需要 prophet 包. 失败时调用方应 fallback 到 SimpleSES."""
    import pandas as pd
    from prophet import Prophet

    df = pd.DataFrame({"ds": [d for d, _ in series], "y": [y for _, y in series]})
    model = Prophet(weekly_seasonality=True, yearly_seasonality=False,
                    interval_width=0.90)
    model.fit(df)
    future = model.make_future_dataframe(periods=horizon)
    pred = model.predict(future).tail(horizon)
    out: list[Forecast] = []
    for _, row in pred.iterrows():
        out.append(Forecast(
            target_date=row["ds"].date(),
            forecast=float(row["yhat"]),
            lower=float(row["yhat_lower"]),
            upper=float(row["yhat_upper"]),
        ))
    # MAPE 用回拟样本
    train_pred = model.predict(df)
    abs_pct = ((df["y"] - train_pred["yhat"]).abs() / df["y"].abs().clip(lower=1)).mean()
    return out, float(abs_pct)


def fit_and_forecast(series: list[tuple[date, float]], horizon: int,
                     use_prophet: bool = False) -> FitResult:
    if use_prophet:
        try:
            fc, mape = fit_with_prophet(series, horizon)
            return FitResult(forecasts=fc, mape=mape)
        except Exception:
            pass   # fall through to SES
    m = SimpleSES().fit(series)
    return FitResult(forecasts=m.predict(horizon), mape=m.mape())
