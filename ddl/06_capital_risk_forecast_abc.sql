-- =====================================================================
-- 资金占用 / 风险 / 预测 / ABC
-- =====================================================================
USE steel_dw;

-- ============================================================
-- 资金占用
-- ============================================================
CREATE TABLE IF NOT EXISTS dws_customer_capital_daily (
  tenant_id            BIGINT       NOT NULL,
  snap_date            DATE         NOT NULL,
  org_id               BIGINT,
  customer_id          BIGINT       NOT NULL,
  ar_amount            DECIMAL(20,2),     -- 客户当日应收
  ap_offset_amount     DECIMAL(20,2),     -- 客户预付(罕见)
  pinned_inv_amount    DECIMAL(20,2),     -- 客户挂账(已下单未提)库存金额
  upstream_ap_offset   DECIMAL(20,2),     -- 该客户对应采购应付占用(分摊)
  capital_occupation   DECIMAL(20,2),     -- ar + pinned_inv - upstream_ap_offset
  funding_rate         DECIMAL(8,6),      -- 适用资金成本率(年化)
  src_update_time      DATETIME
)
DUPLICATE KEY(tenant_id, snap_date, org_id, customer_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ============================================================
-- 风险敞口
-- ============================================================
CREATE TABLE IF NOT EXISTS dws_exposure_daily (
  tenant_id        BIGINT       NOT NULL,
  snap_date        DATE         NOT NULL,
  exposure_type    VARCHAR(16)  NOT NULL,   -- CUSTOMER / ORIGIN / GRADE / HEDGE / SUPPLIER
  entity_id        BIGINT       NOT NULL,
  entity_name      VARCHAR(128),
  exposure_amount  DECIMAL(20,2),
  exposure_tonnage DECIMAL(20,4),
  limit_amount     DECIMAL(20,2),
  limit_tonnage    DECIMAL(20,4),
  utilization      DECIMAL(8,6),
  breach           TINYINT,
  src_update_time  DATETIME
)
DUPLICATE KEY(tenant_id, snap_date, exposure_type, entity_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(entity_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ============================================================
-- 风险/经营建议收件箱
-- ============================================================
CREATE TABLE IF NOT EXISTS advice_inbox (
  inbox_id        BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT,                 -- 个人收件箱(空=按角色路由)
  role            VARCHAR(32),
  category        VARCHAR(16),            -- RISK / ADVICE / ABC / FORECAST
  rule_id         VARCHAR(64)  NOT NULL,
  severity        VARCHAR(8),             -- LOW/MEDIUM/HIGH/CRITICAL
  title           VARCHAR(256),
  payload_json    JSON,                   -- 详细数据 + 建议动作
  status          VARCHAR(16)  DEFAULT 'NEW', -- NEW/READ/ACTED/IGNORED
  created_at      DATETIME,
  expires_at      DATETIME
)
PRIMARY KEY(tenant_id, inbox_id)
DISTRIBUTED BY HASH(tenant_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ============================================================
-- 预测结果
-- ============================================================
CREATE TABLE IF NOT EXISTS dws_forecast_daily (
  tenant_id          BIGINT       NOT NULL,
  run_date           DATE         NOT NULL,
  target_date        DATE         NOT NULL,
  scope_type         VARCHAR(16)  NOT NULL,    -- MATERIAL / ORG / CUSTOMER / OVERALL
  scope_id           VARCHAR(64)  NOT NULL,
  metric_code        VARCHAR(32)  NOT NULL,    -- TON_GP / SALES_TON / INDEX_PRICE / STOCKOUT_RISK / OVERSTOCK_RISK
  forecast_value     DECIMAL(20,4),
  forecast_lower_90  DECIMAL(20,4),
  forecast_upper_90  DECIMAL(20,4),
  model_name         VARCHAR(32),
  model_version      VARCHAR(16),
  mape_30d           DECIMAL(8,6),
  src_update_time    DATETIME
)
DUPLICATE KEY(tenant_id, run_date, target_date, scope_type, scope_id, metric_code)
PARTITION BY RANGE(target_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(scope_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ============================================================
-- 物料 ABC 月度
-- ============================================================
CREATE TABLE IF NOT EXISTS dws_material_abc_monthly (
  tenant_id             BIGINT       NOT NULL,
  snap_month            VARCHAR(7)   NOT NULL,
  material_id           BIGINT       NOT NULL,
  origin_id             BIGINT,
  grade_code            VARCHAR(32),
  product_type          VARCHAR(32),
  rolling_sales_amount  DECIMAL(20,2),
  rolling_sales_tonnage DECIMAL(20,4),
  rank_amount           INT,
  cum_share_amount      DECIMAL(8,6),
  abc_class             VARCHAR(2),         -- A/B/C/D
  velocity_label        VARCHAR(16),        -- FAST/SLOW/DEAD
  last_move_days        INT,
  on_hand_tonnage       DECIMAL(20,4),
  on_hand_amount        DECIMAL(20,2),
  src_update_time       DATETIME
)
PRIMARY KEY(tenant_id, snap_month, material_id)
DISTRIBUTED BY HASH(material_id) BUCKETS 16
PROPERTIES("replication_num"="3");
