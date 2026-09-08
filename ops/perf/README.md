# 压测

## 工具
- k6 (单元/接口压测)
- Locust (复杂业务流压测)

## 运行
```bash
docker run -i --rm grafana/k6 run --vus 100 --duration 5m -e JWT_TOKEN=$JWT - < k6_chat.js
```

## 关键指标 SLA
| 接口 | P95 | 错误率 | 并发 |
|------|-----|--------|------|
| /v1/chat/messages (SSE) | < 5s | < 1% | 100 |
| /v1/dsl/compile | < 200ms | < 0.1% | 200 |
| /v1/briefing/today | < 500ms | < 0.5% | 50 |
| /v1/billing/preauth | < 50ms | < 0.01% | 500 |
