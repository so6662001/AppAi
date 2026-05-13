-- =====================================================================
-- 库存域: 实时余额 + 日快照 + 流水/动因
-- =====================================================================
USE steel_dw;

-- ----------------------------- 实时库存余额 -----------------------------
CREATE TABLE IF NOT EXISTS dwd_inv_balance (
  tenant_id        BIGINT       NOT NULL,
  warehouse_id     BIGINT       NOT NULL,
  warehouse_type   VARCHAR(16),
  material_id      BIGINT       NOT NULL,
  origin_id        BIGINT,
  grade_code       VARCHAR(32),
  batch_no         VARCHAR(64)  NOT NULL,
  coil_no          VARCHAR(64),
  on_hand_qty      DECIMAL(20,4),
  on_hand_tonnage  DECIMAL(20,4),
  available_qty    DECIMAL(20,4),
  available_tonnage DECIMAL(20,4),
  unit_cost        DECIMAL(20,4),
  amount           DECIMAL(20,2),
  last_in_date     DATE,
  last_move_date   DATE,
  src_update_time  DATETIME,
  etl_load_time    DATETIME
)
PRIMARY KEY(tenant_id, warehouse_id, material_id, batch_no)
DISTRIBUTED BY HASH(material_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 日库存快照 (核心) -----------------------------
-- 每日 00:30 物化, 即使无变动也要写, 跨日 AVG 才正确
CREATE TABLE IF NOT EXISTS dws_inv_daily_snapshot (
  tenant_id        BIGINT       NOT NULL,
  snap_date        DATE         NOT NULL,
  org_id           BIGINT,
  warehouse_id     BIGINT,
  warehouse_type   VARCHAR(16),
  material_id      BIGINT,
  origin_id        BIGINT,
  grade_code       VARCHAR(32),
  product_type     VARCHAR(32),
  on_hand_qty      DECIMAL(20,4),
  on_hand_tonnage  DECIMAL(20,4),
  coil_count       INT,
  amount           DECIMAL(20,2),
  avg_cost_price   DECIMAL(12,2),
  aging_days       INT,
  aging_0_30       DECIMAL(20,2),
  aging_31_90      DECIMAL(20,2),
  aging_91_180     DECIMAL(20,2),
  aging_181_365    DECIMAL(20,2),
  aging_365_plus   DECIMAL(20,2),
  last_move_days   INT,
  safety_stock     DECIMAL(20,4),
  demand_30d       DECIMAL(20,4),
  src_update_time  DATETIME
)
DUPLICATE KEY(tenant_id, snap_date, org_id, warehouse_id, material_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(material_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 库存动因 (流水聚合) -----------------------------
CREATE TABLE IF NOT EXISTS dws_inv_movement_daily (
  tenant_id     BIGINT      NOT NULL,
  biz_date      DATE        NOT NULL,
  org_id        BIGINT,
  warehouse_id  BIGINT,
  material_id   BIGINT,
  origin_id     BIGINT,
  grade_code    VARCHAR(32),
  txn_category  VARCHAR(24) NOT NULL,
   /*  PURCHASE_IN / PRODUCTION_IN / CUSTOMER_RETURN_IN
       SALES_OUT / PRODUCTION_OUT / SAMPLE_OUT / SCRAP_OUT / RETURN_TO_SUPPLIER
       TRANSFER_IN / TRANSFER_OUT / ALLOC_IN / ALLOC_OUT
       INVENTORY_GAIN / INVENTORY_LOSS */
  direction     VARCHAR(4)  NOT NULL,     -- IN / OUT
  tonnage       DECIMAL(20,4)             SUM,
  amount        DECIMAL(20,2)             SUM,
  txn_count     INT                       SUM
)
AGGREGATE KEY(tenant_id, biz_date, org_id, warehouse_id, material_id, origin_id, grade_code, txn_category, direction)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(material_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 仓库利用率/堆码 日聚合 -----------------------------
CREATE TABLE IF NOT EXISTS dws_warehouse_daily (
  tenant_id      BIGINT      NOT NULL,
  biz_date       DATE        NOT NULL,
  warehouse_id   BIGINT      NOT NULL,
  used_area      DECIMAL(12,2),
  total_area     DECIMAL(12,2),
  pile_count     INT,
  piece_count    INT
)
DUPLICATE KEY(tenant_id, biz_date, warehouse_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(warehouse_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 盘点结果 -----------------------------
CREATE TABLE IF NOT EXISTS dws_inv_count_monthly (
  tenant_id      BIGINT      NOT NULL,
  biz_month      VARCHAR(7)  NOT NULL,
  warehouse_id   BIGINT,
  material_id    BIGINT,
  book_tonnage   DECIMAL(20,4),
  actual_tonnage DECIMAL(20,4),
  loss_tonnage   DECIMAL(20,4),
  gain_tonnage   DECIMAL(20,4)
)
DUPLICATE KEY(tenant_id, biz_month, warehouse_id, material_id)
DISTRIBUTED BY HASH(material_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 套保头寸日快照 -----------------------------
CREATE TABLE IF NOT EXISTS dws_hedge_position_daily (
  tenant_id          BIGINT      NOT NULL,
  snap_date          DATE        NOT NULL,
  contract_code      VARCHAR(16) NOT NULL,   -- RB/HC/I/J/JM/SS
  underlying_grade   VARCHAR(32),
  underlying_product VARCHAR(32),
  long_tonnage       DECIMAL(20,4),
  short_tonnage      DECIMAL(20,4),
  net_tonnage        DECIMAL(20,4),
  spot_tonnage       DECIMAL(20,4),
  hedge_ratio_target DECIMAL(8,4),
  net_exposure_tonnage DECIMAL(20,4),
  limit_tonnage      DECIMAL(20,4),
  breach             TINYINT,
  unrealized_pnl     DECIMAL(20,2)
)
DUPLICATE KEY(tenant_id, snap_date, contract_code)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(contract_code) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 套保聚合(辅助 hedge_ratio 指标) -----------------------------
CREATE TABLE IF NOT EXISTS dws_hedge_daily (
  tenant_id      BIGINT      NOT NULL,
  snap_date      DATE        NOT NULL,
  inv_tonnage    DECIMAL(20,4),
  short_tonnage  DECIMAL(20,4)
)
DUPLICATE KEY(tenant_id, snap_date)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(tenant_id) BUCKETS 1
PROPERTIES("replication_num"="3");
