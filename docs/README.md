# 钢铁行业 AI 经营分析平台 · 设计文档总览

本仓库包含从指标库到落地组件的完整设计交付物。

## 1. 仓库结构

```
metrics/                         指标库 (语义层 YAML, 共 178 个指标)
  ├─ _common.yaml                公共配置 (时间粒度/格式/客户类型/计费规则)
  ├─ _dimensions.yaml            共享维度 (含产地/材质/挂价/钢种)
  ├─ metrics_sales.yaml          销售 47
  ├─ metrics_inventory.yaml      库存 42 (含日库存/平均库存/周转率/动因)
  ├─ metrics_production.yaml     生产/加工 25
  ├─ metrics_procurement.yaml    采购 14
  ├─ metrics_quality.yaml        质量 14
  ├─ metrics_capital.yaml        资金占用 14 (含客户级 IRR/吨净利)
  ├─ metrics_risk.yaml           风险 10 + 告警规则
  ├─ metrics_forecast.yaml       预测 6 + 行动建议规则
  └─ metrics_abc.yaml            ABC/长尾 6

ddl/                             全量建表脚本
  ├─ 00_database.sql             StarRocks 库 + 账号
  ├─ 01_dimensions.sql           维度表
  ├─ 02_sales.sql                销售域
  ├─ 03_inventory.sql            库存域
  ├─ 04_production_quality.sql   生产/质量
  ├─ 05_procurement.sql          采购
  ├─ 06_capital_risk_forecast_abc.sql  资金/风险/预测/ABC
  ├─ 07_governance.sql           指标治理 (MySQL)
  ├─ 08_billing.sql              计费 (MySQL)
  ├─ 09_chat_session.sql         聊天会话 (MySQL)
  ├─ 10_materialized_views.sql   StarRocks 物化视图
  └─ 11_briefing.sql             AI 早报 (MySQL)

apps/erp-client-guard/           C# SDK:ERP 客户端防 RPA / 防爬取(检测 + 风险评分 + 水印/蜜罐 + 网格护盾)
services/client-guard-service/   其服务端(策略下发 / 独立评分 / 导出审批 token),表见 ddl/22_client_guard.sql

docs/
  ├─ anti-rpa-design.md          防 RPA 威胁模型 / 五层防御 / 局限 / 接入步骤
  ├─ metric-registry/
  │   ├─ README.md               指标注册中心页面原型
  │   ├─ api.openapi.yaml        OpenAPI 接口契约
  │   └─ workflow.md             变更工作流 + 影响分析
  └─ uniapp/
      ├─ ai-briefing.md          AI 经营早报产品设计 + 卡片样例 + 推送规则
      ├─ ai-briefing-api.openapi.yaml  早报接口
      └─ ai-briefing-components.md     uniapp 组件树
```

## 2. 关键设计决策

| 项 | 选择 | 理由 |
|----|------|------|
| OLAP | **StarRocks 3.2 LTS** | MySQL 协议、AI 生成 SQL 友好；既支持点查也支持大宽表 |
| OLTP CDC | **首发 SeaTunnel/DataX 时间窗增量** | SQL Server 2008 不支持 Debezium，先用分钟级增量过渡 |
| LLM | **DeepSeek-V3 + 通义千问 + 本地 Qwen2.5-7B** | 国内合规、便宜；本地小模型省 60-80% API 费 |
| Embedding | **bge-m3 本地** | 离线，无成本 |
| AI 编排 | **LangGraph + 多模型路由 + 多级缓存** | 意图/抽取/总结分级，便宜模型优先 |
| 语义层 | **YAML 元数据 + DSL 编译器** | 杜绝 AI 直接写 SQL 的幻觉，权限可控 |
| 计费 | **Token 包 + 订阅 + 次数包**三种共存 | 适配不同客户认知，业务 Token 与模型 Token 解耦 |
| 部署 | **K8s + Docker** | 标准方式 |

## 3. 累计交付汇总

| 模块 | 交付物 | 量 |
|------|--------|---|
| 指标库 | 9 个域 YAML + 共享配置 | **178 个指标** |
| 数据仓库 DDL | StarRocks 表 + 物化视图 | **35 张表 + 3 个 MV** |
| 业务库 DDL | MySQL 治理/计费/会话/早报 | **27 张表** |
| 指标治理 | 页面原型 + OpenAPI + 工作流 | 6 类页面 / 25 接口 |
| AI 早报 | 产品设计 + 10 类卡片 + OpenAPI + 组件树 | 完整模块 |

## 4. 落地路径建议

**M1 — 数据底座 + 销售域 MVP**
- 部署 StarRocks + MySQL 治理库
- 跑通 SeaTunnel SQL Server → StarRocks 销售相关 10 张表的分钟级增量
- 注册中心上线，先发布 30 个销售域指标
- AI 编排打通 "1 个指标 + 1 个时间维 + 1 个客户维" 的 NL2DSL→SQL

**M2 — 库存域 + 计费**
- 库存日快照、动因表上线
- 钱包 + 三模式计费 + 预扣 Lua 落地
- 余额胶囊、套餐购买在 uniapp 端可用

**M3 — 生产/质量/采购 + 客户级周转**
- 把剩余 100+ 个指标分批发布
- 资金占用、客户 IRR、ABC 长尾上线

**M4 — 预测 + 早报 + 风控告警**
- Prophet / LightGBM 模型上线
- AI 经营早报闭环（生成 → 推送 → 反馈 → 复盘）
- 风控规则 7×24 告警

**M5 — 本地小模型 + 优化**
- 自建 1×4090 跑 Qwen2.5-7B + bge-m3
- 缓存优化、物化视图沉淀
- 模型微调（基于 chat_feedback 的高频好评样本）

## 5. 给客户的承诺

- **数据安全**: 私有化部署、行列权限、SQL 白名单、审计 ≥ 180 天
- **价格透明**: 三种计费模式，业务 Token 不随模型切换变化
- **可观测**: 每条问答都有用量明细 + 模型 + 缓存命中
- **可治理**: 178 个指标都有 Owner，变更走审批，影响可追溯
