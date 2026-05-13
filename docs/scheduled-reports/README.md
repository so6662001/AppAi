# 定时报表（Scheduled Reports）

让用户把"AI 对话/DSL 查询"另存为定时任务，到点自动执行并把结果推送到用户指定的渠道。

## 1. 业务场景

| 角色 | 典型需求 |
|------|---------|
| 钢贸老板 | 每天 08:00 微信收到「昨日销售/库存/吨毛利/资金占用 Top10」 |
| 业务员 | 每天 18:00 收到「我的今日业绩、逾期应收」 |
| 加工厂厂长 | 每天 07:30 钉钉收到「昨日 OEE / 良率 / 工单逾期」 |
| 钢厂厂长 | 每月 1 号 09:00 邮件收到「上月吨钢成本、净利率」 |
| 财务 | 每周一收到「应收账款逾期清单」 |
| 风控 | 实时（条件触发）收到「客户授信突破/套保超限」（由风控引擎承担，复用本系统的推送通道） |

> 风控告警与定时报表共享同一套推送基础设施。

## 2. 系统架构

```
                        ┌─────────────────────────────────────────┐
       创建/编辑        │   用户端                                  │
       订阅 ───────────►│   ▸ uniapp 聊天页「另存为定时报表」对话框  │
                        │   ▸ uniapp「我的定时报表」3 个页面         │
                        │   ▸ 注册中心 Vue「定时报表」管理页         │
                        └─────────────────────────────────────────┘
                                       │ HTTP
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   Java 后端 / scheduler API              │
                        │   ▸ CRUD scheduled_report                │
                        │   ▸ 触发 /run-now                        │
                        │   ▸ 历史 /runs                            │
                        └─────────────────────────────────────────┘
                                       │ MySQL
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   MySQL: scheduled_report,               │
                        │          scheduled_report_run,           │
                        │          scheduled_report_subscription   │
                        │          scheduled_report_template       │
                        └─────────────────────────────────────────┘
                                       │
                                       │ (next_run_at 到点)
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │   report-scheduler (Python)              │
                        │   ▸ APScheduler 每 30s 扫表              │
                        │   ▸ 线程池 (默认 10) 并发执行            │
                        │   ▸ 调 dsl-compiler 编 SQL               │
                        │   ▸ 执行 StarRocks (pymysql)             │
                        │   ▸ 渲染 blocks + 写 chat_message        │
                        │   ▸ 推送 INAPP/WECOM/DINGTALK/EMAIL/UNI  │
                        └─────────────────────────────────────────┘
```

## 3. 数据模型

详见 `ddl/12_scheduled_reports.sql`。要点：

- `scheduled_report`：报表定义，包含 DSL、调度（cron/daily/weekly/...）、渠道、生命周期、计费配置
- `scheduled_report_run`：每次执行的快照（SQL/行数/blocks/总结/推送结果/Token 消耗/error）
- `scheduled_report_subscription`：共享给其他用户的订阅
- `scheduled_report_template`：运营预置模板（首次部署预置 10 个常用模板）

## 4. 用户旅程

### 4.1 从聊天另存

```
用户在 AI 聊天页问完一句:
   "上周华东大区 A 产品达交率"
        │
        ▼
   AI 返回结果, 底部出现「⏰ 保存为定时」按钮
        │
        ▼
   点击 → 弹 SaveAsReportDialog
   ┌──────────────────────────────┐
   │ 名称 [上周华东达交率_____]    │
   │ 频率 [每天][每周][每月][高级] │
   │ 时间 [9:00▼]                  │
   │ 推送 [☑App] [☑企微] [☐邮件]  │
   │       [取消] [保存]            │
   └──────────────────────────────┘
        │
        ▼
   POST /v1/scheduled-reports (source=chat, dsl_json 携带本次聊天的 DSL)
        │
        ▼
   后端生成 next_run_at, scheduler 到点自动跑
        │
        ▼
   到点后:
     ▸ 站内信弹一张早报式卡片
     ▸ 企业微信群推 markdown 消息
     ▸ 聊天会话「我的定时报表」里新增一条 assistant 消息
```

### 4.2 一键订阅模板

```
打开「报表模板」页 → 切「钢贸」Tab → 选「老板日报-销售&库存」→ 点订阅
              ↓
        POST /v1/scheduled-reports/templates/1/subscribe
              ↓
        系统按模板 dsl_json + cron_expr + channels 自动创建一个 scheduled_report
              ↓
        明天 8 点开始每天推送
```

### 4.3 管理（启停/编辑/删除/历史）

- uniapp 端：`pages/scheduled-report/list.vue`
- 注册中心：`/scheduled-reports`

## 5. 调度策略

| 类型 | 用例 | 配置 |
|------|------|------|
| `daily` | 每天 8:00 | 时间选择器 |
| `weekly` | 每周一 9:00 | 时间 + 星期 |
| `monthly` | 每月 1 号 9:00 | 时间 + 日期 |
| `cron` | 高级 | 6 段 cron |
| `once` | 一次性预约 | 只跑 1 次, 跑完 EXPIRED |

`schedule_type ≠ cron` 时由前端拼成标准 cron。后端用 `croniter` 解析。

## 6. 失败与重试

- 单次失败：记录到 `scheduled_report_run`，**不重试**（避免雪崩）
- 连续 3 次失败：自动 `status=PAUSED`，给 Owner 推「报表已暂停」通知
- 调度延迟：扫描 30s 一次，最坏延迟 ≤ 60s

## 7. 计费

- 每次执行调 `dsl-compiler` 拿到 `biz_token_estimate`，写入 `scheduled_report_run.biz_tokens_charged`
- billing-service 异步从 `cost_owner_user_id` 的钱包扣减（默认 = 创建者）
- 失败不扣费
- 推送本身不计费（INAPP 是免费的，外部渠道按用量计费走平台账户）

## 8. 推送渠道实现

详见 `services/report-scheduler/src/report_scheduler/notify.py`：

| 渠道 | 实现 | 必要配置 |
|------|------|----------|
| INAPP | 写 `advice_inbox` 表 | 无 |
| WECOM | 企业微信群机器人 webhook | webhook |
| DINGTALK | 钉钉群机器人 markdown | webhook |
| EMAIL | SSL SMTP | host/port/user/pass/from/to |
| UNI_PUSH | DCloud GetuiPush 接口 | url/token |
| SMS | 待对接阿里云/腾讯云 | accessKey |

## 9. 与 chat_message 集成

每次成功执行后**会写入一条 `assistant` 消息**到 `session_id = "scheduled-{report_id}"` 的会话中。用户在「我的会话」里展开该会话，就能看到这个报表的全部历史结果，并且可以在该会话里继续向 AI 追问。

## 10. 部署

```bash
# 1) 建表
docker exec -i steel-mysql mysql -uroot -p$MYSQL_ROOT_PASSWORD < ddl/12_scheduled_reports.sql

# 2) 起 scheduler
docker build -t steel/report-scheduler:0.1 services/report-scheduler/
docker run -d --name steel-report-scheduler \
  -e DB_URL='mysql+pymysql://root:steeldev@steel-mysql:3306/steel_chat?charset=utf8mb4' \
  -e DSL_COMPILER_URL=http://steel-dsl-compiler:8000 \
  -e SR_JDBC_URL='jdbc:mysql://steel-starrocks:9030/steel_dw' \
  -e SR_USER=root -e TZ=Asia/Shanghai \
  -p 8100:8100 \
  steel/report-scheduler:0.1

# 3) 健康检查
curl http://localhost:8100/health

# 4) 手动触发(调试)
curl -X POST http://localhost:8100/internal/run-now/1
```

## 11. 测试

```bash
cd services/report-scheduler
PYTHONPATH=src pytest -v
# tests/test_cron.py: 6 passed
```

## 12. 后续增强

- [ ] 报表共享（多人订阅）
- [ ] 模板市场 + 收藏/评分
- [ ] 大数据量结果转 Excel，附件方式发邮件
- [ ] AI 总结优化：调便宜模型生成更人话的一句话
- [ ] 异常上报：连续失败 → 推 Owner 钉钉
- [ ] 报表"快照对比"：本次结果 vs 上次结果差异高亮
- [ ] 灰度新版本指标：定时报表自动选 v1 / v2 双跑对比
