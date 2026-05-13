# risk-alert-service

风控告警引擎：周期扫描风险类指标，命中规则后写 `advice_inbox` + 触发推送（复用 report-scheduler 的 `tenant_notify_config`）。

## 规则来源

从 `metrics/metrics_risk.yaml`（以及其他 `metrics_*.yaml` 中的 `alert_rules` 段）加载：

```yaml
alert_rules:
  - id: ALERT_CREDIT_OVER
    metric: credit_utilization_rate
    when: "value > 0.95"
    severity: HIGH
    title: "客户授信使用率超 95%"
    push_to: [客户经理, 风控, 老板]
    cooldown_hours: 12
    advice_template: "客户【{customer_name}】授信使用率 {value}, 建议立即催收"
```

## 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | /health | 健康检查 + 当前规则数 |
| GET | /internal/rules | 列出已加载规则 |
| POST | /internal/scan-now | 手动触发一次全量扫描 |

## 启动

```bash
pip install -e ".[dev]"
export DB_URL='mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4'
export METRICS_DIR=/workspace/metrics
export DSL_COMPILER_URL=http://localhost:8000
export REDIS_HOST=localhost
export SCAN_INTERVAL=3600        # 默认每小时
uvicorn risk_alert.app:app --port 8300
```

## 测试

```bash
PYTHONPATH=src pytest -v
# 10 passed: 表达式 5 + 规则加载 2 + 冷却 3
```

## 冷却

同一 `(tenant, rule, metric)` 在 `cooldown_hours` 内只推送一次。用 Redis `SETNX + EX` 实现，Redis 不可达时降级为"始终允许"避免漏告警。

## 与其他服务的协作

```
[每小时扫描]
   │
   ├─> 拉规则 (metrics_*.yaml alert_rules)
   ├─> 枚举活跃租户 (tenant_wallet)
   ├─> 对每条规则 × 每租户:
   │     ├─> 调 dsl-compiler 编 SQL → 执行获取指标值
   │     ├─> 评估 when 表达式
   │     ├─> 命中: try_acquire 冷却锁
   │     ├─> 写 advice_inbox (供 uniapp 站内信 + AI 早报展示)
   │     └─> 调通知服务 (复用 tenant_notify_config: WECOM/DINGTALK/EMAIL/SMS)
   └─> 完成
```
