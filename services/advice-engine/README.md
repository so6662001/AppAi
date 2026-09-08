# advice-engine

行动建议引擎：扫描 `metrics_forecast.yaml` 中 `action_rules` → 命中后写 `advice_inbox` (category=ADVICE) → 早报次日 ADVICE 卡片展示。

测试：
```
PYTHONPATH=src pytest -v   # 5 passed
```
