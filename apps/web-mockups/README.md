# 钢铁 AI 经营分析平台 · PC 高保真原型

> 用于设计验证, 所有数据均为演示样例.
> 技术: **静态 HTML + Tailwind 调色 + ECharts CDN**, 不依赖后端, 双击即开.

## 如何查看

### 方式 1 · 浏览器直接打开
```bash
# 任何浏览器双击 (Chrome / Edge / Safari)
apps/web-mockups/index.html
```

### 方式 2 · 起本地服务 (推荐, 解决 layout.js 路径问题)
```bash
cd apps/web-mockups
python3 -m http.server 8888
# 然后访问 http://localhost:8888/
```

### 方式 3 · Node 静态服务
```bash
npx serve apps/web-mockups
```

## 原型清单

| # | 文件 | 角色 | 关键交互 |
|---|------|------|---------|
| 0 | `index.html` | 全员 | 16 张原型缩略图导航 |
| **A** | **`role-insight-owner.html`** | **老板** | 健康度雷达 + 4 域分项 + 6 项 AI 待办 + 行业对标 |
| **B** | **`role-insight-sales-rep.html`** | **销售员** | 同事 PK + 5 项个性化短板 + 1 对 1 AI 教练 + 个性化学习 |
| **C** | **`role-insight-finance.html`** | **财务总监** | 7 大 KPI vs 行业 + 5 项合规预警 + AI 财务参谋 |
| **D** | **`metric-drilldown.html`** | **全员** | 任意指标 → 多维拆分 → 明细钻取 → AI 自动归因 |
| 1 | `dashboard-owner.html` | 老板 | 4 KPI + 销售/毛利双轴图 + 风险 + 客户资金 Top + 业务员排名 + 库存动因 |
| 2 | `ai-briefing.html` | 老板 | 6 张早报卡: SUMMARY / 风险 / ADVICE / 期现 / 资金占用 / Token 余额 |
| 3 | `ai-chat.html` | 全员 | 流式对话 + DSL 编译展示 + 图表+表格 + 追问芯片 + 计费 |
| 4 | `commission-detail.html` | 销售员 | 工资条流水 + 14 单规则命中明细 + 6 月趋势 + 同事对比 |
| 5 | `commission-config.html` | 销售总监 | 4 模板选择 + 8 维度规则配置 + Feature Flag 开关 + 试算 |
| 6 | `hedge-board.html` | 老板/期货部 | 现期基差图 + 锁价/点价订单 + 套保头寸 + PnL 三段 + 净敞口 |
| 7 | `consolidation.html` | 财务总监 | 主体树 + 5 主体并列 + 关联交易抵消 + 股权血缘图 |
| 8 | `biz-expense-audit.html` | 财务/合规 | Feature 开关 + 待审批 + 30 天趋势 + 59 笔明细 |
| 9 | `metric-registry.html` | 数据治理 | 13 业务域 + 220 指标 + 详情 / SLA / 血缘 / 变更 |
| 10 | `tenant-onboarding.html` | 新租户 | 3 步向导, 4 业务模式选择, 12 Feature Flag |
| 11 | `finance-statements.html` | 财务总监 | 利润表完整结构 + 暗规则口径 + 健康度 + 行业对标雷达 |

## 风格与不变量

- **配色**: Element Plus (#1677ff) + 钢铁工业蓝灰 (#001529) · 警示 #f5222d / 暖橙 #fa8c16 / 增长绿 #52c41a
- **布局**: 1440 桌面端 · 左 224px 暗色侧栏 + 顶部 56px 白色头部
- **字体**: PingFang SC + Helvetica · 数字用 tabular-nums 等宽
- **图表**: ECharts 5.5 · 标准化 ToolBox 隐藏, 配色与品牌色一致
- **数据**: 真实业务粒度 (订单号 / 客户名脱敏 / 金额单位明确)

## 真实可点击的交互

虽然是静态 HTML, 但我们把以下交互设计成 "感觉" 真实:
- 侧栏菜单高亮 + 跳转 (12 张原型互通)
- 表格 hover / 排序按钮 / 筛选下拉
- Tab 切换 (利润表 / 资产负债 / 现金流)
- Feature Flag 真 switch (CSS-only)
- 业务模式 / 提成模板的卡片选中态
- 早报 6 张卡的不同 severity 色带
- AI 对话 SSE 流式提示动效

## 与后端关系

每张原型对应的后端服务在 PR #1 已实现:

| 原型 | 后端服务 |
|------|---------|
| ai-briefing | `briefing-service` + `advice-engine` + `risk-alert-service` |
| ai-chat | `chat-orchestrator` + `dsl-compiler` + `query-engine` |
| commission-* | `commission-service` |
| hedge-board | StarRocks 4 张 hedge 表 + dws_basis_daily |
| consolidation | `dim_legal_entity` + `fact_intercompany_tx_daily` + 合并视图 |
| biz-expense-audit | `fact_biz_expense` + `biz_expense_limit` |
| metric-registry | `metric-registry-service` |
| tenant-onboarding | `tenant_profile` + `tenant_feature_flag` + 4 模板 |
| finance-statements | `dws_income_statement_monthly` 等 4 张报表表 |
| role-insight-* | `role-insight-service` + `role_profile` + `industry_benchmark` + `insight_rule` |
| metric-drilldown | `role-insight-service.drilldown` + `metric_drilldown_path` |
