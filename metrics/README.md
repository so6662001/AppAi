# 指标库（钢铁行业 AI 经营分析平台）

## 1. 概览

178 个指标，覆盖 9 大域，按 SemVer 版本管理。所有 YAML 是**语义层（Semantic Layer / Metric Layer）的合同**，AI 不直接写 SQL，而是输出"指标 + 维度 + 过滤 + 时间"的 DSL，由后端 DSL 编译器翻译成 SQL。

```
_common.yaml              公共配置（时间粒度、格式、客户类型、行业枚举、计费规则）
_dimensions.yaml          共享维度定义（含产地/材质/挂价/钢种）
metrics_sales.yaml        销售域       47 个 (基础 25 + 挂价 6 + 其他收入 6 + 其他支出 6 + 净利 4)
metrics_inventory.yaml    库存域       42 个 (基础 22 + 日库存/周转 10 + 库存动因 10)
metrics_production.yaml   生产/加工域  25 个
metrics_procurement.yaml  采购域       14 个
metrics_quality.yaml      质量域       14 个
metrics_capital.yaml      资金占用域   14 个 (资金占用 8 + 客户级周转 6)
metrics_risk.yaml         风险域       10 个 + 告警规则
metrics_forecast.yaml     预测域        6 个 + 行动建议规则
metrics_abc.yaml          ABC/长尾      6 个 + 周报洞察
```

## 2. 指标编码规则

- `MNNN` 全局唯一，3 位以内顺序号；M001-M100 为通用业务指标；M101+ 为钢铁行业扩展指标。
- 编号一旦发布即冻结，废弃指标保留编号 + `status: DEPRECATED`。
- `name` 是给程序/SQL/DSL 用的英文蛇形，`label` 是中文展示名。
- `synonyms` 是 AI 语义路由的备选词，所有口语/俗语都加进去。

## 3. 关键字段说明

| 字段 | 含义 |
|------|------|
| `code` | 全局指标编号，对应注册中心主键 |
| `fact` | 主要事实表 |
| `formula` | 计算表达式（支持 SQL 聚合 + `requires_metrics` 引用） |
| `semantics` | additive / snapshot / dimension / virtual |
| `time_agg` | snapshot 跨日时如何聚合：sum/avg/first/last |
| `requires_metrics` | 依赖的上游指标（自动展开） |
| `applicable` | 适用客户类型 TRADE/PROCESS/MILL（缺省=全部）|
| `sensitivity` | LOW/MEDIUM/HIGH 影响计费与权限 |
| `bizToken_multiplier` | 业务 Token 计费乘数 |
| `owner` | 业务侧负责人 |
| `version` | 语义版本号 |
| `status` | DRAFT / REVIEW / APPROVED / PUBLISHED / DEPRECATED |

## 4. 半累积语义（库存类必看）

```
semantics: snapshot
time_agg: avg | first | last   # 跨日聚合方式
```

DSL 编译器看到 `snapshot` 时：
- **单日**: 直接 SUM 仓 × SKU 时点值
- **跨日**: 按 time_agg 处理，禁止 SUM (会膨胀)
- **平均库存**: 先按日 SUM、再跨日 AVG，顺序不可换

## 5. 派生指标展开

```
requires_metrics: [a, b]
formula: "(a - b) / NULLIF(c, 0)"
```

编译器递归展开 ≤ 3 层，循环依赖直接报错。

## 6. 工具命令（建议在仓库里加）

```bash
# 校验所有 YAML 语法 + 引用闭环 + Owner 必填
make validate-metrics

# 列出某域指标
make list-metrics DOMAIN=sales

# 影响分析: 修改 net_profit 会影响哪些下游/会话/看板
make impact METRIC=net_profit

# 一键发布到 metric_def 表
make publish-metrics
```
