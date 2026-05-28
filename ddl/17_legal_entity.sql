-- =====================================================================
-- 多法人主体支持 (有些客户多主体, 有些单主体)
-- 主体维 + 关联交易 + 合并抵消
-- =====================================================================

-- ----------------------------- 法人主体维 (StarRocks) -----------------------------
USE steel_dw;

CREATE TABLE IF NOT EXISTS dim_legal_entity (
  tenant_id        BIGINT       NOT NULL,
  entity_id        BIGINT       NOT NULL,
  entity_code      VARCHAR(64),
  entity_name      VARCHAR(256),
  short_name       VARCHAR(64),
  uscc             VARCHAR(32),                -- 统一社会信用代码
  entity_type      VARCHAR(16),                -- TRADE/PROCESS/MILL/SHELL/HOLDING
  business_line    VARCHAR(16),                -- 主营 TRADE/PROCESS/MILL/SHELL
  parent_entity_id BIGINT,                     -- 母公司
  ownership_pct    DECIMAL(8,4),               -- 母公司持股比例 (用于权益法)
  consolidation_method VARCHAR(16),            -- FULL(全合并)/EQUITY(权益)/NONE
  region           VARCHAR(64),
  -- 财务设置
  base_currency    VARCHAR(8)    DEFAULT 'CNY',
  fiscal_year_start VARCHAR(5)   DEFAULT '01-01',
  tax_rate         DECIMAL(8,4)  DEFAULT 0.1300,    -- 增值税率
  income_tax_rate  DECIMAL(8,4)  DEFAULT 0.2500,    -- 企业所得税率
  -- 关联识别
  is_related_party TINYINT       DEFAULT 0,    -- 是否关联方
  -- 状态
  is_active        TINYINT       DEFAULT 1,
  established_date DATE,
  closed_date      DATE,
  etl_load_time    DATETIME
)
PRIMARY KEY (tenant_id, entity_id)
DISTRIBUTED BY HASH(entity_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 关联交易识别表 -----------------------------
-- 将客户/供应商映射到法人主体, 识别"自家人跟自家人"的交易
CREATE TABLE IF NOT EXISTS dim_party_entity_map (
  tenant_id      BIGINT       NOT NULL,
  party_type     VARCHAR(16)  NOT NULL,         -- CUSTOMER/SUPPLIER
  party_id       BIGINT       NOT NULL,
  entity_id      BIGINT,                        -- 如果该 party 就是自家某主体则非空
  is_related     TINYINT      DEFAULT 0,
  related_reason VARCHAR(128),
  effective_from DATE,
  effective_to   DATE,
  etl_load_time  DATETIME
)
PRIMARY KEY (tenant_id, party_type, party_id, effective_from)
DISTRIBUTED BY HASH(party_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 关联交易事实 (按销售/采购单标记) -----------------------------
CREATE TABLE IF NOT EXISTS fact_intercompany_tx_daily (
  tenant_id        BIGINT       NOT NULL,
  tx_date          DATE         NOT NULL,
  tx_type          VARCHAR(16)  NOT NULL,         -- SALES/PURCHASE/TRANSFER/SERVICE_FEE/INTEREST/RENT
  source_entity_id BIGINT       NOT NULL,         -- 卖方 (我方主体)
  target_entity_id BIGINT       NOT NULL,         -- 买方 (我方另一主体)
  doc_no           VARCHAR(64),
  material_id      BIGINT,
  product_type     VARCHAR(32),
  tonnage          DECIMAL(20,4),
  amount_excl_tax  DECIMAL(20,2),
  tax_amount       DECIMAL(20,2),
  amount_incl_tax  DECIMAL(20,2),
  cost_basis       DECIMAL(20,2),                -- 卖方对应成本
  -- 合并抵消标记
  is_eliminated    TINYINT      DEFAULT 0,        -- 月结合并时是否已抵消
  eliminate_run_id BIGINT,
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, tx_date, tx_type, source_entity_id, target_entity_id)
PARTITION BY RANGE (tx_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(source_entity_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 合并抵消批次 -----------------------------
CREATE TABLE IF NOT EXISTS dws_consolidation_run (
  tenant_id       BIGINT       NOT NULL,
  run_id          BIGINT       NOT NULL,
  period_month    VARCHAR(7)   NOT NULL,
  run_status      VARCHAR(16),                  -- RUNNING/SUCCESS/FAILED
  eliminate_amount DECIMAL(20,2),
  eliminate_tons   DECIMAL(20,4),
  trigger_user_id  BIGINT,
  started_at       DATETIME,
  finished_at      DATETIME,
  log_text         VARCHAR(4000)
)
DUPLICATE KEY (tenant_id, run_id)
DISTRIBUTED BY HASH(run_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 给主要事实/汇总表增加 entity_id (向后兼容) -----------------------------
-- StarRocks ALTER TABLE ADD COLUMN: 不会回填, ETL 在写入时填充
-- 单主体租户可统一默认 entity_id = tenant_id 或 0
ALTER TABLE dwd_sales_order_line     ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_sales_daily          ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_ar_snapshot          ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_inv_daily_snapshot   ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_purchase_daily       ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_ap_snapshot          ADD COLUMN IF NOT EXISTS entity_id BIGINT;
ALTER TABLE dws_customer_capital_daily ADD COLUMN IF NOT EXISTS entity_id BIGINT;
