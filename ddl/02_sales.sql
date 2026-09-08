-- =====================================================================
-- 销售域: DWD 明细 + DWS 宽表 + 损益附加表
-- =====================================================================
USE steel_dw;

-- ----------------------------- 销售订单行明细 -----------------------------
CREATE TABLE IF NOT EXISTS dwd_sales_order_line (
  tenant_id           BIGINT       NOT NULL,
  order_id            BIGINT       NOT NULL,
  line_no             INT          NOT NULL,
  order_no            VARCHAR(64),
  order_date          DATE,
  customer_id         BIGINT,
  org_id              BIGINT,
  sales_owner_id      BIGINT,
  material_id         BIGINT,
  origin_id           BIGINT,
  grade_code          VARCHAR(32),
  product_type        VARCHAR(32),
  spec_thk            DECIMAL(10,3),
  spec_wid            DECIMAL(10,2),
  qty                 DECIMAL(20,4),
  tonnage             DECIMAL(20,4),
  unit_price          DECIMAL(20,4),     -- 实际成交价(元/吨)
  amount_excl_tax     DECIMAL(20,4),
  tax_amount          DECIMAL(20,4),
  amount_incl_tax     DECIMAL(20,4),
  cost_amount         DECIMAL(20,4),     -- 移动加权成本
  cost_price          DECIMAL(20,4),
  listed_price_snapshot DECIMAL(20,4),   -- 落地当日挂价, 避免跨表 Join
  promise_date        DATE,
  delivered_qty       DECIMAL(20,4),
  delivered_tonnage   DECIMAL(20,4),
  delivered_date      DATE,
  status              VARCHAR(16),
  cancel_flag         TINYINT,
  src_update_time     DATETIME,
  etl_load_time       DATETIME
)
PRIMARY KEY(tenant_id, order_id, line_no)
PARTITION BY RANGE(order_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(order_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 发货明细 -----------------------------
CREATE TABLE IF NOT EXISTS dwd_sales_delivery (
  tenant_id       BIGINT      NOT NULL,
  delivery_id     BIGINT      NOT NULL,
  delivery_no     VARCHAR(64),
  delivery_date   DATE,
  order_id        BIGINT,
  line_no         INT,
  customer_id     BIGINT,
  material_id     BIGINT,
  origin_id       BIGINT,
  grade_code      VARCHAR(32),
  warehouse_id    BIGINT,
  qty             DECIMAL(20,4),
  tonnage         DECIMAL(20,4),
  amount          DECIMAL(20,4),
  is_on_time      TINYINT,
  src_update_time DATETIME,
  etl_load_time   DATETIME
)
PRIMARY KEY(tenant_id, delivery_id)
PARTITION BY RANGE(delivery_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(delivery_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 销售日宽表 (核心) -----------------------------
-- 聚合粒度: 日 × 组织 × 业务员 × 客户 × 物料 × 产地 × 材质 × 产品大类
CREATE TABLE IF NOT EXISTS dws_sales_daily (
  tenant_id           BIGINT       NOT NULL,
  biz_date            DATE         NOT NULL,
  org_id              BIGINT       NOT NULL,
  sales_owner_id      BIGINT,
  customer_id         BIGINT,
  material_id         BIGINT,
  origin_id           BIGINT,
  grade_code          VARCHAR(32),
  product_type        VARCHAR(32),
  order_count         INT                                SUM,
  order_qty           DECIMAL(20,4)                      SUM,
  order_tonnage       DECIMAL(20,4)                      SUM,
  order_amount        DECIMAL(20,2)                      SUM,
  delivered_qty       DECIMAL(20,4)                      SUM,
  delivered_tonnage   DECIMAL(20,4)                      SUM,
  delivered_amount    DECIMAL(20,2)                      SUM,
  cost_amount         DECIMAL(20,2)                      SUM,
  cost_price          DECIMAL(20,4)                      REPLACE,
  gross_profit        DECIMAL(20,2)                      SUM,
  listed_price_snapshot DECIMAL(20,4)                    REPLACE,
  on_time_tonnage     DECIMAL(20,4)                      SUM,
  promise_tonnage     DECIMAL(20,4)                      SUM,
  cancel_tonnage      DECIMAL(20,4)                      SUM,
  return_tonnage      DECIMAL(20,4)                      SUM,
  deliver_lead_days   DECIMAL(10,2)                      REPLACE
)
AGGREGATE KEY(tenant_id, biz_date, org_id, sales_owner_id, customer_id, material_id, origin_id, grade_code, product_type)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 销售其他损益归集 -----------------------------
CREATE TABLE IF NOT EXISTS dws_sales_extra_pnl_daily (
  tenant_id     BIGINT      NOT NULL,
  biz_date      DATE        NOT NULL,
  org_id        BIGINT,
  customer_id   BIGINT,
  material_id   BIGINT,
  origin_id     BIGINT,
  grade_code    VARCHAR(32),
  order_id      BIGINT,
  pnl_category  VARCHAR(32) NOT NULL,
  direction     VARCHAR(8)  NOT NULL,    -- INCOME / EXPENSE
  amount        DECIMAL(20,2)            SUM,
  src_update_time DATETIME               REPLACE
)
AGGREGATE KEY(tenant_id, biz_date, org_id, customer_id, material_id, origin_id, grade_code, order_id, pnl_category, direction)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 应收账款快照 -----------------------------
CREATE TABLE IF NOT EXISTS dws_ar_snapshot (
  tenant_id     BIGINT      NOT NULL,
  snap_date     DATE        NOT NULL,
  org_id        BIGINT,
  customer_id   BIGINT,
  ar_amount     DECIMAL(20,2),
  overdue_amount DECIMAL(20,2),
  overdue_0_30  DECIMAL(20,2),
  overdue_31_60 DECIMAL(20,2),
  overdue_61_90 DECIMAL(20,2),
  overdue_90_plus DECIMAL(20,2),
  src_update_time DATETIME
)
DUPLICATE KEY(tenant_id, snap_date, org_id, customer_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 客户日聚合 -----------------------------
CREATE TABLE IF NOT EXISTS dws_customer_daily (
  tenant_id        BIGINT       NOT NULL,
  biz_date         DATE         NOT NULL,
  customer_id      BIGINT       NOT NULL,
  org_id           BIGINT,
  sales_owner_id   BIGINT,
  order_count      INT                  SUM,
  order_amount     DECIMAL(20,2)        SUM,
  order_tonnage    DECIMAL(20,4)        SUM,
  first_order_date DATE                 REPLACE
)
AGGREGATE KEY(tenant_id, biz_date, customer_id, org_id, sales_owner_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_customer_monthly (
  tenant_id        BIGINT      NOT NULL,
  biz_month        VARCHAR(7)  NOT NULL,
  customer_id      BIGINT      NOT NULL,
  total_customers  INT                  REPLACE,
  repeat_customers INT                  REPLACE
)
AGGREGATE KEY(tenant_id, biz_month, customer_id)
DISTRIBUTED BY HASH(customer_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 点价未结 -----------------------------
CREATE TABLE IF NOT EXISTS dws_pricing_open (
  tenant_id     BIGINT      NOT NULL,
  snap_date     DATE        NOT NULL,
  customer_id   BIGINT,
  material_id   BIGINT,
  origin_id     BIGINT,
  grade_code    VARCHAR(32),
  open_tonnage  DECIMAL(20,4),
  contract_no   VARCHAR(64)
)
DUPLICATE KEY(tenant_id, snap_date, customer_id, material_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 期间费用月度 -----------------------------
CREATE TABLE IF NOT EXISTS dws_period_expense_monthly (
  tenant_id    BIGINT      NOT NULL,
  biz_month    VARCHAR(7)  NOT NULL,
  org_id       BIGINT      NOT NULL,
  expense_type VARCHAR(32) NOT NULL,     -- SELLING / ADMIN / FINANCE
  amount       DECIMAL(20,2)
)
PRIMARY KEY(tenant_id, biz_month, org_id, expense_type)
DISTRIBUTED BY HASH(org_id) BUCKETS 4
PROPERTIES("replication_num"="3");
