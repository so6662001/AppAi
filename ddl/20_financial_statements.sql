-- =====================================================================
-- 标准财务报表 (利润表 + 资产负债表 + 现金流量表) - DWS 层
-- 按 (tenant_id, entity_id, period_month) 粒度
-- 既支持单主体, 又支持多主体合并 (entity_id = 0 = 合并报表)
-- =====================================================================
USE steel_dw;

-- ----------------------------- 科目维 -----------------------------
CREATE TABLE IF NOT EXISTS dim_account (
  tenant_id     BIGINT       NOT NULL,
  account_code  VARCHAR(32)  NOT NULL,
  account_name  VARCHAR(128),
  category      VARCHAR(32),                  -- ASSET/LIAB/EQUITY/REVENUE/COST/EXPENSE/TAX/OI
  sub_category  VARCHAR(64),                  -- 流动资产/非流动资产/营业收入/营业成本/...
  parent_code   VARCHAR(32),
  level         INT,
  is_leaf       TINYINT,
  is_active     TINYINT      DEFAULT 1,
  etl_load_time DATETIME
)
PRIMARY KEY (tenant_id, account_code)
DISTRIBUTED BY HASH(account_code) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 总账明细 (从 ERP 同步) -----------------------------
CREATE TABLE IF NOT EXISTS fact_gl_daily (
  tenant_id      BIGINT       NOT NULL,
  entity_id      BIGINT,
  tx_date        DATE         NOT NULL,
  voucher_no     VARCHAR(64),
  account_code   VARCHAR(32),
  debit_amount   DECIMAL(20,2) DEFAULT 0,
  credit_amount  DECIMAL(20,2) DEFAULT 0,
  net_amount     DECIMAL(20,2) DEFAULT 0,           -- = debit - credit
  doc_type       VARCHAR(16),                       -- SALES/PURCHASE/PAYMENT/ADJUST
  doc_no         VARCHAR(64),
  remark         VARCHAR(512),
  src_update_time DATETIME
)
DUPLICATE KEY (tenant_id, tx_date, entity_id, account_code, voucher_no)
PARTITION BY RANGE (tx_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(entity_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 利润表 (月) -----------------------------
CREATE TABLE IF NOT EXISTS dws_income_statement_monthly (
  tenant_id          BIGINT       NOT NULL,
  entity_id          BIGINT       NOT NULL,         -- 0=合并
  period_month       VARCHAR(7)   NOT NULL,
  revenue            DECIMAL(20,2),        -- 营业收入
  revenue_main       DECIMAL(20,2),        --   主营 (钢材/加工)
  revenue_other      DECIMAL(20,2),        --   其他 (运费/利息/汇兑)
  cost_of_sales      DECIMAL(20,2),        -- 营业成本
  gross_profit       DECIMAL(20,2),        -- 毛利
  gross_margin_pct   DECIMAL(8,6),
  selling_expense    DECIMAL(20,2),        -- 销售费用
  admin_expense      DECIMAL(20,2),        -- 管理费用
  finance_expense    DECIMAL(20,2),        -- 财务费用 (利息净)
  biz_fee_expense    DECIMAL(20,2),        -- 业务费 (暗规则口径)
  roundoff_expense   DECIMAL(20,2),
  kickback_in        DECIMAL(20,2),
  kickback_out       DECIMAL(20,2),
  hedge_pnl          DECIMAL(20,2),        -- 套保盈亏
  other_income       DECIMAL(20,2),
  other_expense      DECIMAL(20,2),
  operating_profit   DECIMAL(20,2),        -- 营业利润
  ebitda             DECIMAL(20,2),
  ebt                DECIMAL(20,2),        -- 利润总额
  income_tax         DECIMAL(20,2),
  net_profit         DECIMAL(20,2),        -- 净利
  net_margin_pct     DECIMAL(8,6),
  -- 调整与审计
  is_audited         TINYINT       DEFAULT 0,
  data_source        VARCHAR(16),              -- ERP/GL/DERIVED
  src_update_time    DATETIME
)
PRIMARY KEY (tenant_id, entity_id, period_month)
DISTRIBUTED BY HASH(entity_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 资产负债表 (月末快照) -----------------------------
CREATE TABLE IF NOT EXISTS dws_balance_sheet_monthly (
  tenant_id          BIGINT       NOT NULL,
  entity_id          BIGINT       NOT NULL,
  period_month       VARCHAR(7)   NOT NULL,
  -- 资产
  cash_and_equiv     DECIMAL(20,2),
  ar_amount          DECIMAL(20,2),
  prepay_amount      DECIMAL(20,2),
  other_receivable   DECIMAL(20,2),
  inventory_amount   DECIMAL(20,2),
  current_assets     DECIMAL(20,2),
  fixed_assets       DECIMAL(20,2),
  intangible_assets  DECIMAL(20,2),
  noncurrent_assets  DECIMAL(20,2),
  total_assets       DECIMAL(20,2),
  -- 负债
  st_borrowing       DECIMAL(20,2),
  ap_amount          DECIMAL(20,2),
  contract_liab      DECIMAL(20,2),
  other_payable      DECIMAL(20,2),
  current_liab       DECIMAL(20,2),
  lt_borrowing       DECIMAL(20,2),
  noncurrent_liab    DECIMAL(20,2),
  total_liab         DECIMAL(20,2),
  -- 权益
  paid_in_capital    DECIMAL(20,2),
  retained_earnings  DECIMAL(20,2),
  total_equity       DECIMAL(20,2),
  -- 衍生指标
  current_ratio      DECIMAL(8,4),         -- 流动比
  quick_ratio        DECIMAL(8,4),         -- 速动比
  debt_to_asset      DECIMAL(8,4),
  inv_turnover_days  DECIMAL(8,2),
  ar_turnover_days   DECIMAL(8,2),
  ap_turnover_days   DECIMAL(8,2),
  ccc_days           DECIMAL(8,2),         -- 现金循环天数
  is_audited         TINYINT       DEFAULT 0,
  data_source        VARCHAR(16),
  src_update_time    DATETIME
)
PRIMARY KEY (tenant_id, entity_id, period_month)
DISTRIBUTED BY HASH(entity_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 现金流量表 (月) -----------------------------
CREATE TABLE IF NOT EXISTS dws_cashflow_monthly (
  tenant_id          BIGINT       NOT NULL,
  entity_id          BIGINT       NOT NULL,
  period_month       VARCHAR(7)   NOT NULL,
  cf_operating       DECIMAL(20,2),         -- 经营活动现金流
  cf_investing       DECIMAL(20,2),
  cf_financing       DECIMAL(20,2),
  cf_net             DECIMAL(20,2),
  cash_begin         DECIMAL(20,2),
  cash_end           DECIMAL(20,2),
  -- 关键明细
  cash_from_sales    DECIMAL(20,2),
  cash_to_purchase   DECIMAL(20,2),
  tax_paid           DECIMAL(20,2),
  interest_paid      DECIMAL(20,2),
  interest_received  DECIMAL(20,2),
  src_update_time    DATETIME
)
PRIMARY KEY (tenant_id, entity_id, period_month)
DISTRIBUTED BY HASH(entity_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 员工价值贡献月度 -----------------------------
-- 把"员工"作为一个口径, 跟客户/物料并列, 用于:
--   1) 工资条对账
--   2) 员工净贡献 (毛利 - 自己用掉的资金成本 - 工资 - 业务费)
USE steel_dw;
CREATE TABLE IF NOT EXISTS dws_employee_contrib_monthly (
  tenant_id          BIGINT       NOT NULL,
  entity_id          BIGINT,
  period_month       VARCHAR(7)   NOT NULL,
  employee_id        BIGINT       NOT NULL,
  role               VARCHAR(32),
  -- 业绩
  revenue            DECIMAL(20,2) DEFAULT 0,
  tonnage            DECIMAL(20,4) DEFAULT 0,
  gross_profit_listed DECIMAL(20,2) DEFAULT 0,
  -- 资金成本占用
  avg_ar_balance     DECIMAL(20,2),
  ar_interest_cost   DECIMAL(20,2),
  avg_inv_balance    DECIMAL(20,2),
  inv_interest_cost  DECIMAL(20,2),
  avg_prepay_balance DECIMAL(20,2),
  prepay_interest_cost DECIMAL(20,2),
  -- 各项支出
  biz_fee_amt        DECIMAL(20,2) DEFAULT 0,
  roundoff_amt       DECIMAL(20,2) DEFAULT 0,
  commission_amt     DECIMAL(20,2) DEFAULT 0,
  base_salary_amt    DECIMAL(20,2) DEFAULT 0,
  social_amt         DECIMAL(20,2) DEFAULT 0,
  -- 净贡献
  net_contribution   DECIMAL(20,2) DEFAULT 0,
  contribution_rank  INT,
  src_update_time    DATETIME
)
PRIMARY KEY (tenant_id, period_month, employee_id)
DISTRIBUTED BY HASH(employee_id) BUCKETS 8
PROPERTIES("replication_num"="3");
