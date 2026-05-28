# 钢铁行业 4 类业务模式 - 系统适配说明

> 客户画像: 10-500 人, 同时存在钢贸+加工+钢厂+皮包公司, 多主体也单主体, 有期现结合, **没有** 垫资/保兑仓/保理.
> 财务跑我们自己的 ERP. 暗规则 (业务费/抹零) **租户级开关**, 默认关闭.

## 1. 业务模式画像

| 模式  | 关键词        | 库存 | 期现 | 多主体 | 提成基数      | 主要指标包                |
|-------|---------------|------|------|--------|---------------|---------------------------|
| TRADE | 钢贸现货      | 有   | 可选 | 可选   | 挂牌毛利      | PK_TRADE_OWNER + 销售包   |
| PROCESS | 加工厂      | 有   | 少   | 通常单 | 加工费 + 毛利 | PK_PROCESS_OWNER          |
| MILL  | 钢厂自销      | 有   | 多   | 多     | 吨毛利元/吨   | PK_MILL_OWNER             |
| SHELL | 皮包/纯撮合   | 无   | 无   | 单     | 撮合差价      | PK_SHELL_OWNER + Broker   |

启用方式: 在 `tenant_profile` 表填 `primary_business` + `sub_business_lines (JSON)`, 系统按其推送相应 metric_pack.

## 2. 关键 Feature Flag (`tenant_feature_flag`)

| flag_code              | 默认 | 影响                                                       |
|------------------------|------|------------------------------------------------------------|
| `ENABLE_BIZ_FEE`       | OFF  | 是否启用业务费建模 (`fact_biz_expense` 写入)              |
| `ENABLE_ROUNDOFF`      | OFF  | 是否启用抹零建模                                          |
| `ENABLE_KICKBACK`      | OFF  | 是否启用返点 (上下游) 建模                                |
| `ENABLE_HEDGE`         | OFF  | 是否启用锁价/点价/套保模块                                |
| `ENABLE_INTERCOMPANY`  | OFF  | 是否启用多法人合并/关联交易抵消                           |
| `ENABLE_AR_INTEREST`   | ON   | 提成扣应收资金成本                                        |
| `ENABLE_INV_INTEREST`  | ON   | 提成扣库存资金成本                                        |
| `ENABLE_PREPAY_INTEREST`| ON  | 提成扣预付款资金成本                                      |
| `ENABLE_PROFIT_VOLUME_SEG`| ON| 客群分群 (利润型 vs 走量型) 不同系数                      |
| `ENABLE_DIRECT_INDIRECT`| ON  | 直销 / 间销 / 转单 不同系数                               |
| `ENABLE_SHELL_MODE`    | OFF  | 皮包公司精简模式 (隐藏库存相关卡)                         |

入口: 后台 `/system/features` (gateway → metric-registry-service.RbacController), 操作需审计.

## 3. 提成引擎 (commission-service)

### 设计要点
- **数学结构稳定 + 参数可变**: 4 套真实数字模板内置, 租户在 UI 改参数即落库.
- **完全可配置**: 一个租户可有多个 scheme (TRADE 走 1#, PROCESS 走 2#, 同一员工跨方案累加).
- **优先级匹配**: 按 (sales_mode, settle_type, customer_seg, product_type, origin, grade_family, org, margin_band) 8 维匹配, 短路第一条.
- **审计可解释**: 每次计算输出 `explain_trace` (工资条可直接展示) + `calc_detail_json` (审计留痕).

### 真实数字默认模板

```yaml
# TRADE 钢贸现货
基数: 挂牌毛利
默认: 30%
   ↳ 直销+现款+利润型 35%
   ↳ 直销+T+30+利润型 32%
   ↳ 直销+走量型      25%
   ↳ 间销/转单        15%
扣减: 应收/库存/预付资金成本 (0.0125% / 0.015% / 0.0125% 每天)
保底: 3000 / 月
封顶: 无

# PROCESS 加工厂
基数: 加工费收入
默认: 15%
加工费独立计提, 钢材买卖部分套 TRADE 同口径
保底: 3500 / 月

# MILL 钢厂自销
基数: 吨毛利 (元/吨)
默认: 50 元/吨, 全员不分客群
保底: 5000 / 月

# SHELL 皮包公司
基数: 撮合差价 × 吨
默认: 50% (直接撮合) / 20% (挂单转单中介)
不扣资金成本 (没库存)
保底: 1500 / 月
```

### 调整链 (公式)
```
原始提成 = 基数 × rate × 直销系数 × 客群系数
扣减     = AR利息 + INV利息 + PREPAY利息 + 业务费 + 抹零
计算值   = max(0, 原始 - 扣减)
最终     = clamp(计算值, floor, cap)
```

### 客群系数 (启用 `ENABLE_PROFIT_VOLUME_SEG` 时)
| 客群    | 系数 | 业务含义                  |
|---------|------|---------------------------|
| PROFIT  | 1.2  | 利润型客户, 鼓励 hard sell|
| VOLUME  | 0.8  | 走量型客户, 抑制冲量提成 |
| STRATEGIC | 1.0| 战略客户, 维持系数       |
| A/B/C   | 1.1/1.0/0.7 | 经典 RFM 等级       |

### 直销/间销系数 (启用 `ENABLE_DIRECT_INDIRECT` 时)
| sales_mode | 系数 | 业务含义              |
|------------|------|-----------------------|
| DIRECT     | 1.0  | 直销, 全额计提        |
| INDIRECT   | 0.5  | 间销/挂单, 半提       |
| TRANSIT    | 0.3  | 纯转单中介, 三折      |
| SHELL      | 1.0  | 皮包业务员, 全额      |

## 4. 期现结合 (启用 `ENABLE_HEDGE` 时)

### 锁价订单 (`fact_locked_price_order`)
客户跟我方锁定一口价, 我方对外开期货空单对冲. 关键指标:
- `locked_unhedged_tonnage` (已锁未对冲吨数, 单边敞口预警)
- `hedge_realized_pnl` / `hedge_unrealized_pnl`

### 点价订单 (`fact_spot_price_order` + `fact_spot_price_pick`)
客户在窗口期内分批点价, 价格 = 期货价 + 约定基差.
- `spot_open_tonnage` (未点价吨数)
- `spot_pick_progress` (点价完成率)
- `spot_avg_pick_basis` (加权平均基差)

### 套保头寸 (`dws_hedge_position_detail_daily`)
按主体 × 合约 × 月份 × 多空方向, 单独 PnL 拆分.

### 基差 (`dws_basis_daily`)
- `basis_current` (当前基差)
- `basis_invert_days` (基差倒挂天数)

### PnL 拆分 (`dws_hedge_pnl_split_daily`)
- `spot_pnl` (现货段)
- `futures_pnl` (期货段)
- `basis_pnl` (基差贡献)
- `combined_pnl` (总盈亏)

## 5. 多主体合并 (启用 `ENABLE_INTERCOMPANY` 时)

### 维度
- `dim_legal_entity` — 法人主体 + 合并方法 (FULL/EQUITY/NONE)
- `dim_party_entity_map` — 客户/供应商 → 法人主体映射, 识别关联方

### 事实表都加 `entity_id`
- `dwd_sales_order_line.entity_id`
- `dws_inv_daily_snapshot.entity_id`
- `dws_purchase_daily.entity_id`
- ...

### 抵消
- 关联交易写 `fact_intercompany_tx_daily`, 月结跑 `dws_consolidation_run` 抵消, 销售/成本同步去重.
- 报表查询: `WHERE entity_id = 0` 出合并表, `WHERE entity_id = X` 出单体.

## 6. 业务费 / 抹零 / 返点 (暗规则)

### 默认关闭, 必须显式打开
管理员后台 `/system/features` 把 `ENABLE_BIZ_FEE`/`ENABLE_ROUNDOFF`/`ENABLE_KICKBACK` 改为 ON.
**任何写入都强制留 operator_id + audited_at**, 且超过上限自动走审批.

### 上限规则模板 (`biz_expense_limit`)
| 类型          | 单据上限 | 单据占毛利上限 | 月度上限 | 超此走审批 | 审批角色           |
|---------------|----------|----------------|----------|------------|---------------------|
| BIZ_FEE       | 5000     | 20%            | 30000    | 3000       | SALES_DIRECTOR      |
| ROUNDOFF      | 500      | 2%             | 5000     | 1000       | FINANCE_MGR         |
| KICKBACK_OUT  | 20000    | 30%            | 100000   | 10000      | CEO                 |

### 数据进入提成
- `fact_biz_expense.affect_commission = 1` (默认开) → 该业务员当期提成基数扣除
- 关闭则只进财务费用, 不动提成

## 7. 财务三表 (`dws_income_statement_monthly`, `dws_balance_sheet_monthly`, `dws_cashflow_monthly`)

按 (tenant_id, entity_id, period_month) 粒度.
- `entity_id > 0` = 单体报表
- `entity_id = 0` = 合并报表 (从单体 + `fact_intercompany_tx_daily` 抵消 派生)

财务总监指标包 `PK_FINANCE_CONTROLLER` 默认订阅 6 张报表: 利润表 / 资产负债表 / 现金流 / 关联交易 / 暗规则审计 / 提成审计.

## 8. 员工净贡献 (`dws_employee_contrib_monthly`)

按 (tenant, period_month, employee) 粒度:
```
净贡献 = 个人毛利
       - 个人占用应收×资金成本
       - 个人占用库存×资金成本
       - 个人预付×资金成本
       - 个人业务费/抹零
       - 提成
       - 基础工资
       - 社保
```
工资条 + 360 评估 + 老板视角"谁是真正赚钱的人"使用.

## 9. 三套指标包模板组合

| 业务模式 | 老板包                  | 业务员包                | 财务包                          |
|----------|-------------------------|-------------------------|---------------------------------|
| TRADE    | PK_TRADE_OWNER          | PK_TRADE_SALES_REP      | PK_FINANCE_CONTROLLER           |
| PROCESS  | PK_PROCESS_OWNER        | PK_PROCESS_PRODUCTION_MGR | PK_FINANCE_CONTROLLER         |
| MILL     | PK_MILL_OWNER           | PK_MILL_VP              | PK_FINANCE_CONTROLLER           |
| SHELL    | PK_SHELL_OWNER (新)     | PK_SHELL_BROKER (新)    | PK_FINANCE_CONTROLLER           |

## 10. 已**不再**支持的业务 (避免误导)

- 垫资业务 (代客户先付钱给上游)
- 保兑仓 (银行+仓储+核心企业三方协议)
- 应收账款保理 (转让给保理公司)

若未来需要, 沿用 `tenant_feature_flag` 增加 `ENABLE_FINANCING`/`ENABLE_FACTORING` 即可, 暂不实施.
