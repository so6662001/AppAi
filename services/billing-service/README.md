# billing-service (Spring Boot 3 + Java 17)

钱包计费服务：把 `services/billing-lua/*.lua` 加载到 Redis，对外暴露预扣 / 结算 / 释放 / 退款 / 充值 / 查询 REST 接口；异步写 MySQL `usage_record` 与 `billing_ledger`。

## 接口

| Method | Path | 说明 |
|--------|------|------|
| GET | /billing/wallet/{tid} | 余额 |
| POST | /billing/wallet/{tid}/recharge | 充值 |
| POST | /billing/preauth | 预扣 (返回 reservation + plan) |
| POST | /billing/settle | 结算 (多退少补) |
| POST | /billing/release | 释放预扣 |
| POST | /billing/refund | 退款 |

## 启动

```bash
mvn package
# 把 services/billing-lua 挂到 /app/billing-lua, 容器内 LUA_DIR 指向它
java -DLUA_DIR=$(pwd)/../billing-lua -jar target/billing-service-0.1.0.jar
```

Docker：

```bash
docker build -t steel/billing-service:0.1 .
docker run -d -p 8081:8081 \
  -e DB_URL='jdbc:mysql://mysql:3306/steel_billing?...' \
  -e REDIS_HOST=redis -e REDIS_PORT=6379 \
  -v $(pwd)/../billing-lua:/app/billing-lua:ro \
  steel/billing-service:0.1
```

## 自动清扫

`ReservationSweeper` 每 30s 扫一次 `usage_reservation` 中 `status='HELD' AND expires_at < NOW()` 的记录，调用 `release.lua` 全额退还（解决用户中断未结算的场景）。

## 测试

```bash
mvn test
# 6 passed (Mockito mock 掉 Redis + LuaScriptManager)
```

## 接入

被 `chat-orchestrator` / `report-scheduler` / `risk-alert-service` 等需要计费的服务调用：

```python
# Python 调用示例 (chat-orchestrator)
import httpx
r = httpx.post("http://billing-service:8081/api/v1/billing/preauth", json={
    "tenant_id": 1, "user_id": 10,
    "session_id": "s1", "message_id": "m1",
    "estimate": 2000, "need_times": False, "allow_overrun": False,
})
reservation = r.json()      # {reservationId, plan, ...}
# ... 执行 LLM ...
httpx.post("http://billing-service:8081/api/v1/billing/settle", json={
    "tenant_id": 1,
    "reservation_id": reservation["reservationId"],
    "actual": 1740,
    "model_name": "deepseek-v3",
    "input_tokens": 800, "output_tokens": 470,
    "query_rows": 182, "cache_hit": False,
})
```
