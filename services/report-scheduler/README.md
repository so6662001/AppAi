# Report Scheduler · 定时报表调度器

让用户把 AI 对话或 DSL 查询保存为定时任务，后台自动执行并把结果推送给指定用户。

## 架构

```
[用户] -- 聊天 / 选模板 -- > scheduled_report  (MySQL)
                                    │
                                    │ (next_run_at 到点)
                                    ▼
   ┌─────────────── report-scheduler ────────────────┐
   │  APScheduler 每 30s 扫描 due 报表               │
   │     ↓                                            │
   │  线程池并发执行 (默认 10 个)                     │
   │     ├─ 调 dsl-compiler 编译 SQL                  │
   │     ├─ pymysql 执行 StarRocks                    │
   │     ├─ 渲染 blocks (kpi/table/chart/summary)     │
   │     ├─ 写 scheduled_report_run + chat_message    │
   │     └─ 推送 INAPP/WECOM/DINGTALK/EMAIL/UNI_PUSH  │
   │     ↓                                            │
   │  计算下次执行时间 (croniter)                     │
   └──────────────────────────────────────────────────┘
                                    │
                                    ▼
                          [推送到用户/群]
```

## 启动

```bash
cd services/report-scheduler
pip install -e ".[dev]"
export DB_URL="mysql+pymysql://root:steeldev@localhost:3306/steel_chat?charset=utf8mb4"
export DSL_COMPILER_URL=http://localhost:8000
uvicorn report_scheduler.app:app --port 8100
```

或 Docker:

```bash
docker build -t steel/report-scheduler:0.1 .
docker run -d -p 8100:8100 \
  -e DB_URL=... -e DSL_COMPILER_URL=... \
  steel/report-scheduler:0.1
```

## 测试

```bash
PYTHONPATH=src pytest -v
# 6 passed
```

## 调度策略

| schedule_type | cron_expr | 含义 |
|---------------|-----------|------|
| `cron` | 6 段 cron, 如 `0 0 8 * * ?` | 标准 cron |
| `daily` | 留空(默认 8:00) 或自定义 `0 0 9 * * ?` | 每天 |
| `weekly` | 留空(默认周一 8:00) 或 `0 0 8 ? * MON` | 每周 |
| `monthly` | 留空(默认每月 1 号 8:00) 或 `0 0 9 1 * ?` | 每月 |
| `once` | — | 只跑一次, 执行完自动 EXPIRED |

## 推送渠道

| 渠道 | 必要配置 | 说明 |
|------|----------|------|
| `INAPP` | 无 | 写 `advice_inbox`, uniapp 站内信弹窗 |
| `WECOM` | `webhook` | 企业微信群机器人 markdown |
| `DINGTALK` | `webhook` | 钉钉群机器人 markdown |
| `EMAIL` | `smtp_host/user/pass/from/to` | SSL SMTP |
| `UNI_PUSH` | `uni_push_url/token` | DCloud uni-push, click 跳 uniapp 内页 |
| `SMS` | 待对接 | 阿里云/腾讯云 SDK |

各租户配置存 `tenant_notify_config` 表（待加），从那里查 webhook/SMTP 凭证。

## 失败处理

- 连续 3 次失败 → 自动 `status=PAUSED`，通知 owner
- 单次失败仅记录到 `scheduled_report_run`，不影响下一次调度
- 每次 run 写 `error_code` / `error_msg` 便于排查

## 计费

每次执行调用 `dsl-compiler` 时返回 `biz_token_estimate`，写入 `scheduled_report_run.biz_tokens_charged`，由 billing-service 异步从对应用户的钱包扣减（默认 `cost_owner_user_id = user_id`）。

## 与 chat_message 集成

每次成功执行都会插入一条 `assistant` 消息到 `session_id = "scheduled-{report_id}"` 的会话中。用户在聊天页打开 **「我的定时报表」** 即可看到所有历史结果。
