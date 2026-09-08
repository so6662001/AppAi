# SeaTunnel 同步任务

SQL Server 2008 → StarRocks 数据管道。鉴于 SQL Server 2008 不支持 Debezium，采用**时间窗增量 + 全量重算**两种策略组合。

## 任务清单

| 文件 | 调度频率 | 策略 | 关键依赖 |
|------|---------|------|---------|
| `sales_orders.conf` | 5 分钟 | 时间窗增量 (`LastModifiedTime`) | 业务表加索引 |
| `inventory_balance.conf` | 5 分钟 | 时间窗增量 | 业务库 `LastModifiedTime` |
| `inventory_movement.conf` | 15 分钟 | 时间窗增量 + 聚合 | InventoryTransaction 流水 |
| `work_order.conf` | 10 分钟 | 时间窗增量（仅 PROCESS/MILL） | MES |
| `quality_inspection.conf` | 15 分钟 | 时间窗增量 | QualityInspection |
| `dim_customer.conf` | 每天 02:00 | 全量重算 | 维表量小 |
| `dws_inv_daily_snapshot.conf` | 每天 00:30 | StarRocks 内部 ETL（必须每日跑） | dwd_inv_balance |

## 执行

```bash
# 环境变量
export MSSQL_HOST=10.0.1.20 MSSQL_PORT=1433 MSSQL_DB=ERP_PROD
export MSSQL_USER=etl_readonly MSSQL_PASS=***
export SR_FE_NODES=sr-fe-1:8030,sr-fe-2:8030
export SR_FE_JDBC="jdbc:mysql://sr-fe-1:9030/steel_dw"
export SR_USER=etl_writer SR_PASS=***
export TENANT_ID=1
export SYNC_FROM="2026-05-13 00:00:00"
export SYNC_TO="2026-05-13 00:05:00"

# 运行一个任务
$SEATUNNEL_HOME/bin/seatunnel.sh \
  --config /workspace/data-pipelines/seatunnel/sales_orders.conf
```

## 调度建议（DolphinScheduler 工作流）

```
[业务库时间游标读取] → [for each 任务: 注入 sync_window_from/to] → [并行执行]
                                                                  ↓
                                                          [写回状态表 last_synced_at]
                                                                  ↓
                                                          [触发 DWS 聚合 ETL]
                                                                  ↓
                                                          [Kafka event → AI 编排刷新缓存]
```

## SQL Server 业务库前置改造

为支持时间窗增量，业务表必须有 `LastModifiedTime` 字段并带索引：

```sql
-- 在 SQL Server 上执行
ALTER TABLE dbo.SalesOrderLine ADD LastModifiedTime DATETIME DEFAULT GETDATE();
CREATE INDEX IX_SalesOrderLine_LastMod ON dbo.SalesOrderLine(LastModifiedTime);

-- 业务系统更新时维护该列, 或加触发器
CREATE TRIGGER trg_SalesOrderLine_LastMod ON dbo.SalesOrderLine
AFTER UPDATE AS
BEGIN
  UPDATE sol SET LastModifiedTime = GETDATE()
  FROM dbo.SalesOrderLine sol INNER JOIN inserted i ON sol.OrderID = i.OrderID AND sol.LineNo = i.LineNo;
END;
```

> 推荐尽快将 SQL Server 升到 2019/2022 或迁 PostgreSQL，切换到 Flink CDC 实现秒级延迟。

## 容错与重跑

- 每个任务幂等：StarRocks 主键模型 / 聚合模型自动合并
- 失败重跑：状态表回退到上一次成功的 `last_synced_at`，重新拉取该窗口
- 数据校验：每天对照业务库行数差异告警（>1% 触发，阈值可调）
