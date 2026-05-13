# API Gateway (Spring Cloud Gateway)

统一入口 + JWT 鉴权 + 路由到 8 个下游服务 + CORS + 限流。

## 路由

| Path | → Service |
|------|-----------|
| /v1/dsl/** | dsl-compiler |
| /v1/chat/** | chat-orchestrator |
| /v1/briefing/** | briefing-service |
| /v1/scheduled-reports/**, /v1/notify-configs/** | report-service |
| /v1/billing/** | billing-service |
| /v1/payment/** | payment-service |
| /api/registry/** | metric-registry-service |

## 鉴权

`Authorization: Bearer <jwt>` 必须，白名单除外：
- `/health`, `/actuator/**`
- `/v1/auth/login`
- `/v1/payment/notify/**` (支付回调由第三方验签)

JWT 内容会被解出并注入到下游 header：
- `X-Tenant-Id`, `X-User-Id`, `X-Business-Line`, `X-Role`

## 登录获取 JWT

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"demo","tenant_id":1,"business_line":"TRADE"}'
```

返回 `{token, type:"Bearer", expires_in:86400}`。

## 启动

```bash
mvn package
JWT_SECRET="$(openssl rand -hex 32)" java -jar target/gateway-*.jar
```

## 测试

```bash
mvn test    # 2 passed
```
