# client-guard-service (端口 8980)

ERP 客户端防 RPA 的**服务端**:客户端 SDK(`apps/erp-client-guard`)上报的分值不可信,这里独立重算并做硬约束。

| 接口 | 说明 |
|---|---|
| `GET /v1/policy?tenant_id=` | 策略下发(租户覆盖 → 租户 0 默认 → 内置默认) |
| `PUT /v1/policy/{tenant_id}` | 管理员更新策略(version 自增,客户端据此刷新) |
| `POST /v1/events` | 批量遥测(幂等 by event_id)→ 服务端评分 → 返回 `directive: none/degrade/lock` |
| `GET /v1/risk/{tenant}/{user}` | 当前服务端评分与分解、配额用量 |
| `POST /v1/export/request` | 导出申请:锁定/配额/单次上限 → 拒绝;风险 Low 且行数 ≤ 阈值(或可信设备)→ 自动签发 token;否则 pending |
| `GET /v1/export/request/{id}` | 轮询审批状态 |
| `POST /v1/export/request/{id}/decide` | 审批人决定(不能自审) |
| `GET /v1/export/requests?tenant_id=&status=` | 审批列表(registry-web 用,不含 token) |
| `GET /v1/export/verify` | 校验 token(客户端 / 业务后端) |
| `POST /v1/export/consume` | **业务后端生成 Excel 前调用**:校验 + 一次性消费 + 记账 |
| `POST /v1/export/record` | 小批量导出完成后记账 |
| `PUT /v1/devices/{t}/{u}/{d}/directive` | 人工锁定 / 解锁 / 标记可信设备 |

## 服务端独有信号

- `MultiDeviceConcurrent`:同一账号 5 分钟内 ≥ 2 台设备活动(账号共享给 RPA 机器)
- `ServerExportQuota`:服务端账本超配额
- `OffHoursBulk`:6 小时内 ≥ 3 次非工作时间(北京 22:00~07:00)导出

## 环境变量

| 变量 | 说明 |
|---|---|
| `DB_URL_GOV` | MySQL(`ddl/22_client_guard.sql`);不设则内存存储(仅开发) |
| `GUARD_APPROVAL_SECRET` | 审批 token HMAC 密钥(生产必改) |

## 测试

```bash
pip install -e .[dev] && pytest -q     # 15 passed
```

`tests/test_approval.py::test_known_vector_matches_csharp` 与 C# 侧 `ApprovalTokenVerifier` 测试共用同一 token 向量,保证跨语言兼容。
