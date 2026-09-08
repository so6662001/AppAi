# 角色化指标包 (Metric Packs)

每个包代表一个角色看到的指标视野。共 25 个预置包。

## 文件命名

```
pack_<business_line>_<role_code>.yaml
  - business_line: trade / process / mill / common
  - role_code:     业务角色英文
```

## 加载

`metric-registry-service` 启动时通过 `MetricPackLoader` 把这些 YAML 写入 `metric_pack` 表。
用户 Onboarding 选定角色后, 后端自动给用户绑定对应包。

## 结构

每个 YAML 含:
- `metrics`: 完整可见指标列表 (10-50 个 metric.name)
- `summary_kpis`: 早报 SUMMARY 卡 4 个核心 KPI
- `briefing_cards`: 默认显示的早报卡片类型
- `recommended_questions`: 10 条角色化推荐问题
- `default_subscriptions`: 默认订阅的报表模板 id
- `default_dashboard`: 默认看板路径
- `auth_required`: 此包需要哪些 scope (自动从指标聚合, 也可手填)

## 命名约定

- ID 前缀 `PK_`
- 大写蛇形: `PK_<BIZ>_<ROLE>` 如 `PK_TRADE_SALES_REP`
