# report-service (Spring Boot 3 + Java 17)

定时报表 CRUD 服务，实现 `docs/scheduled-reports/api.openapi.yaml` 中全部接口。

## 启动

```bash
cd services/report-service
mvn spring-boot:run
# 或:
mvn package && java -jar target/report-service-0.1.0.jar
```

环境变量：

| 变量 | 默认 | 含义 |
|------|------|------|
| `PORT` | 8080 | HTTP 端口 |
| `DB_URL` | `jdbc:mysql://localhost:3306/steel_chat?...` | MySQL 连接 |
| `DB_USER` / `DB_PASS` | `root` / `steeldev` | 数据库账号 |
| `SCHEDULER_URL` | `http://localhost:8100` | report-scheduler 地址（用于 run-now） |

## Docker

```bash
docker build -t steel/report-service:0.1 .
docker run -d -p 8080:8080 -e DB_URL=... steel/report-service:0.1
```

## 测试

```bash
mvn test
# 6 passed
```

H2 内存库 + Spring MockMvc 集成测试，无需依赖 MySQL。

## 接口清单

详见 `docs/scheduled-reports/api.openapi.yaml`。前缀 `/api/v1`。

| Method | Path | 说明 |
|--------|------|------|
| GET | /scheduled-reports | 我的报表列表（分页） |
| POST | /scheduled-reports | 新建 |
| GET | /scheduled-reports/{id} | 详情 |
| PATCH | /scheduled-reports/{id} | 编辑（cron 变更自动重算 next_run_at） |
| DELETE | /scheduled-reports/{id} | 软删 |
| POST | /scheduled-reports/{id}/pause | 暂停 |
| POST | /scheduled-reports/{id}/resume | 恢复 |
| POST | /scheduled-reports/{id}/run-now | 立即触发（调 scheduler） |
| GET | /scheduled-reports/{id}/runs | 执行历史 |
| GET | /scheduled-reports/runs/{run_id} | 单次详情（含 blocks） |
| GET | /scheduled-reports/templates | 模板列表 |
| POST | /scheduled-reports/templates/{id}/subscribe | 一键订阅模板 |
| —————— | —————— | —————— |
| GET | /notify-configs | 租户通知配置列表 |
| POST | /notify-configs | 新建（WECOM/DINGTALK/EMAIL...） |
| PATCH | /notify-configs/{id} | 编辑 |
| DELETE | /notify-configs/{id} | 删除 |

## 鉴权

开发期通过请求头模拟：

```
X-Tenant-Id: 1
X-User-Id: 10
```

生产环境应解析 JWT，在 `AuthContext` 里替换实现即可。

## 架构

```
[uniapp / Vue Web] --HTTP--> report-service (Spring Boot)
                                    │
                                    │ JDBC
                                    ▼
                              MySQL steel_chat
                              (scheduled_report*
                               tenant_notify_config)
                                    │
                              POST /internal/run-now
                                    │
                                    ▼
                              report-scheduler (Python)
```

## 与 report-scheduler 的协作

- 这边只做 CRUD + 计算 `next_run_at`
- report-scheduler 每 30s 扫表，到点执行
- `POST /scheduled-reports/{id}/run-now` 通过 HTTP 通知 scheduler 立刻执行（调度器不可达时返回 PENDING 也不影响业务，scheduler 下一轮扫描会自然触发）

## 计费集成（TODO）

- `create()` 时调 dsl-compiler 预估 `biz_token_estimate` 写 `estimated_biz_tokens`
- scheduler 每次执行后由 billing-service 异步从 `cost_owner_user_id` 钱包扣减
