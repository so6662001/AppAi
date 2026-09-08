# forecast-service

时间序列预测服务，输出写入 `dws_forecast_daily` 表，供 AI 早报、定时报表、AI 经营建议引擎消费。

## 两套模型

| 模型 | 何时用 | 优点 | 缺点 |
|------|-------|------|------|
| **Prophet** | `USE_PROPHET=true` 启用 | 周期/节假日/趋势分解强 | 需要 cmdstanpy, 镜像 800MB+ |
| **SimpleSES** | 默认 | 零依赖, 启动即用; 单测全覆盖 | 不识别周期 |

设计上**自动降级**：若 `USE_PROPHET=true` 但 prophet 装载失败，自动 fallback 到 SimpleSES，永不阻塞业务。

## 训练接口

```bash
curl -X POST http://localhost:8400/v1/forecast/fit -H "Content-Type: application/json" -d '{
  "series": [
    {"ds":"2026-01-01","y":100}, {"ds":"2026-01-02","y":102}, ...
  ],
  "horizon": 7
}'
```

返回：

```json
{
  "horizon": 7,
  "mape": 0.062,
  "model": "SES",
  "forecasts": [
    {"target_date":"2026-05-14","forecast":158.3,"lower":153.1,"upper":163.5},
    ...
  ]
}
```

## 调度

- 每周一 `02:00` 全量重训（所有 metric × 所有 scope）
- 每天 `04:00` 增量更新
- 结果落 `dws_forecast_daily`

## 启动

```bash
pip install -e ".[dev]"          # 默认 SES
# 或:
pip install -e ".[dev,prophet]"  # 启用 Prophet (需要联网装 cmdstanpy)
export USE_PROPHET=false
uvicorn forecast_service.app:app --port 8400
```

## 测试

```bash
PYTHONPATH=src pytest -v
# 8 passed: SES 拟合 + CI 扩张 + 短序列异常 + Prophet fallback + Runner 行生成
```

## 集成

- `AI 经营早报` ForecastCard 读 `dws_forecast_daily` 显示下周吨毛利预测
- `定时报表` 模板「下周吨毛利预测」直接 SELECT `forecast_ton_gross_profit_nextweek` 指标
- `AI 建议引擎` 用 `forecast_index_price_nextweek` + `daily_inv_tonnage` 触发"加快出货 / 惜售"建议
