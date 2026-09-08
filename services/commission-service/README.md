# commission-service · 钢铁行业租户级提成引擎

## 设计目标

每个钢贸/加工/钢厂/皮包公司租户的提成规则 **几乎都不一样**, 但 **数学结构是稳定的**.
本服务把"结构"做成代码, 把"参数+规则"做成 DB 配置, 让租户用 UI 配置出符合自己实情的方案.

## 核心结构

```
方案 (scheme)
  ├── 基数类型: 挂牌毛利 / 吨毛利 / 净利 / 加工费 / 销售额 / 撮合差价
  ├── 默认系数 + 默认利率 (应收/库存/预付)
  ├── 5 个开关 (是否启用客群/直销/业务费/抹零/各利息)
  ├── 保底 / 封顶
  └── 规则明细 (rule_line) × N
        ├── 维度匹配 (sales_mode / settle / customer_seg / product / origin / org / margin_band)
        └── 命中后的 rate + rate_unit
```

## 4 套内置真实数字模板

| 业务模式 | scheme_code           | 基数             | 默认系数           | 保底  |
|----------|-----------------------|------------------|--------------------|-------|
| 钢贸     | TPL_TRADE_GP30        | 挂牌毛利         | 30% (利润型35%)    | 3000  |
| 加工厂   | TPL_PROCESS_FEE15     | 加工费收入       | 15%                | 3500  |
| 钢厂     | TPL_MILL_TONNAGE      | 吨毛利           | 50 元/吨           | 5000  |
| 皮包公司 | TPL_SHELL_SPREAD      | 撮合差价         | 50% (转单 20%)     | 1500  |

## 计算公式 (简化)

```
foreach order:
    base   = base_of(order)               # 由 scheme.base_type 决定
    rule   = match_rule(order, rules)     # 按 priority 找第一条
    rate   = rule.rate if rule else scheme.rate_default
    adj_di = 1.0 / 0.5 / 0.3              # 直销/间销/转单
    adj_seg= 1.2 / 0.8 / 1.0              # 利润型/走量型/战略

    raw_one = base * rate * adj_di * adj_seg  # PCT
            或 = tonnage * rate * adj_di * adj_seg # YUAN_PER_TON

raw_sum = SUM(raw_one)
deduct  = ar_interest + inv_interest + prepay_interest + biz_fee + roundoff
calc    = max(0, raw_sum - deduct)
final   = clamp(calc, floor, cap)
```

## API

| 端点                                | 用途                                                     |
|-------------------------------------|----------------------------------------------------------|
| `GET  /v1/templates`                | 列出 4 套内置模板 (新租户开户时选)                       |
| `GET  /v1/templates/{business_line}`| 拉取某业务线的方案 + 规则明细                            |
| `POST /v1/calc`                     | 给定方案 + 规则 + 订单列表, 输出 CommissionResult        |
| `POST /v1/calc/by-template`         | 直接套用内置模板试算 (Demo)                              |

## 关键不变量

1. **无副作用 calculate()** — 输入 dataclass, 输出 Pydantic, 不读 DB. 复算友好.
2. **explain_trace** — 每次计算输出一串可读说明, 工资条直接展示.
3. **优先级匹配** — 短路第一条, 避免多规则叠加歧义.
4. **关闭开关 = 系数 1.0** — `use_customer_seg=False` 时即视为所有客户系数 1.0, 不影响数学.
