# StarRocks 全量 DDL 脚本

按编号执行即可完成数据仓库 + 业务库（治理/计费/会话）的全量建表。

```
00_database.sql                StarRocks 数据库与账号
01_dimensions.sql              维度表 (含产地/材质/挂价/客户授信/期间费用规则/钢材指数)
02_sales.sql                   销售域: dwd + dws + 其他损益 + 应收 + 期间费用月度
03_inventory.sql               库存: 余额 + 日快照 + 动因流水 + 套保头寸
04_production_quality.sql      生产/加工 (工单/OEE/能耗/成本) + 质量
05_procurement.sql             采购: PO + 收货 + IQC + 应付
06_capital_risk_forecast_abc.sql  资金占用 + 风险敞口 + 建议收件箱 + 预测 + ABC
07_governance.sql              指标治理 (MySQL): metric_def + 版本/变更/审批/订阅/质量
08_billing.sql                 计费 (MySQL): 套餐/钱包/订阅/预扣/用量/账本/对账
09_chat_session.sql            聊天 (MySQL): 会话/消息/反馈/推荐问题
10_materialized_views.sql      StarRocks 异步物化视图加速高频查询
11_briefing.sql                AI 早报模板与历史
12_scheduled_reports.sql       定时报表模板/任务/订阅/分发记录
13_tenant_notify_config.sql    租户通知通道配置 (webhook/SMTP/SMS)
14_rbac.sql                    RBAC 用户/角色/权限/行级 ACL
15_metric_pack.sql             角色化指标包 + 用户偏好 + 临时授权 + 权限申请
16_tenant_config.sql           租户业务模式 + 特性开关 + 提成方案/规则 + 客群/销售员归属
17_legal_entity.sql            多法人主体 + 关联交易 + 合并抵消
18_hedge.sql                   期现结合: 锁价/点价/套保头寸/基差/PnL 拆分
19_biz_expense.sql             业务费/抹零/返点 (暗规则建模, 默认关闭)
20_financial_statements.sql    标准财务三表 (利润/资产负债/现金流) + 员工净贡献
21_role_insight.sql            岗位智能画像 + 行业基准 + 诊断规则 + 钻取路径 + 快照
```

## 数据库分布

| 数据库 | 引擎 | 用途 |
|--------|------|------|
| `steel_dw` | StarRocks 3.2 | 数据仓库, 跑分析查询 |
| `steel_governance` | MySQL 8.0 | 指标注册中心、审计 |
| `steel_billing` | MySQL 8.0 | 钱包/计费/订单 |
| `steel_chat` | MySQL 8.0 | 会话历史 |
| `steel_app` (沿用现有) | SQL Server 2008 → 推荐 2022 | 业务库 (ERP/MES/WMS) |

## 关键设计要点

1. **所有事实表都有 `tenant_id` 作为第一列**，编译器强制注入，杜绝跨租户串数据。
2. **大表按月分区**，便于历史归档与冷热分层。
3. **物料/客户/供应商用 `_his` 拉链表**，处理慢变维。
4. **库存日快照**：即使无变动也每天写一行，跨日 AVG 才准。
5. **挂价快照字段** `listed_price_snapshot` 落地在 `dwd_sales_order_line` 与 `dws_sales_daily`，避免每次 Join。
6. **AGGREGATE 模型**优先用于 dws 宽表（SUM/REPLACE 自动合并），**Primary Key 模型**用于 dim 与有 upsert 的 dwd。
7. **物化视图**异步刷新，DSL 编译器看到匹配的指标 + 维度 + 时间粒度直接路由到 MV。

## 执行顺序

```bash
# StarRocks
mysql -h fe-host -P 9030 -u root -p < 00_database.sql
mysql -h fe-host -P 9030 -u root -p < 01_dimensions.sql
mysql -h fe-host -P 9030 -u root -p < 02_sales.sql
mysql -h fe-host -P 9030 -u root -p < 03_inventory.sql
mysql -h fe-host -P 9030 -u root -p < 04_production_quality.sql
mysql -h fe-host -P 9030 -u root -p < 05_procurement.sql
mysql -h fe-host -P 9030 -u root -p < 06_capital_risk_forecast_abc.sql
mysql -h fe-host -P 9030 -u root -p < 10_materialized_views.sql

# MySQL
mysql -h mysql-host -u root -p < 07_governance.sql
mysql -h mysql-host -u root -p < 08_billing.sql
mysql -h mysql-host -u root -p < 09_chat_session.sql
mysql -h mysql-host -u root -p < 11_briefing.sql
mysql -h mysql-host -u root -p < 12_scheduled_reports.sql
mysql -h mysql-host -u root -p < 13_tenant_notify_config.sql
mysql -h mysql-host -u root -p < 14_rbac.sql
mysql -h mysql-host -u root -p < 15_metric_pack.sql
mysql -h mysql-host -u root -p < 16_tenant_config.sql   # 多租户 + 提成 + 客群
mysql -h mysql-host -u root -p < 19_biz_expense.sql     # 暗规则上限规则部分
mysql -h mysql-host -u root -p < 21_role_insight.sql    # 岗位画像 + 行业基准 + 钻取路径

# StarRocks (新增的多主体/期现/财务报表)
mysql -h fe-host -P 9030 -u root -p < 17_legal_entity.sql
mysql -h fe-host -P 9030 -u root -p < 18_hedge.sql
mysql -h fe-host -P 9030 -u root -p < 19_biz_expense.sql   # fact_biz_expense 部分
mysql -h fe-host -P 9030 -u root -p < 20_financial_statements.sql
```
