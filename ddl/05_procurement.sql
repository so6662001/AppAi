-- =====================================================================
-- 采购域
-- =====================================================================
USE steel_dw;

CREATE TABLE IF NOT EXISTS dwd_purchase_order_line (
  tenant_id      BIGINT      NOT NULL,
  po_id          BIGINT      NOT NULL,
  line_no        INT         NOT NULL,
  po_no          VARCHAR(64),
  po_date        DATE,
  supplier_id    BIGINT,
  org_id         BIGINT,
  material_id    BIGINT,
  origin_id      BIGINT,
  grade_code     VARCHAR(32),
  qty            DECIMAL(20,4),
  tonnage        DECIMAL(20,4),
  unit_price     DECIMAL(20,4),
  amount         DECIMAL(20,2),
  promise_date   DATE,
  received_qty   DECIMAL(20,4),
  received_tonnage DECIMAL(20,4),
  received_date  DATE,
  status         VARCHAR(16),
  is_overdue     TINYINT,
  src_update_time DATETIME
)
PRIMARY KEY(tenant_id, po_id, line_no)
PARTITION BY RANGE(po_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(po_id) BUCKETS 16
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dwd_purchase_receipt (
  tenant_id    BIGINT      NOT NULL,
  receipt_id   BIGINT      NOT NULL,
  po_id        BIGINT,
  line_no      INT,
  receipt_date DATE,
  warehouse_id BIGINT,
  material_id  BIGINT,
  origin_id    BIGINT,
  grade_code   VARCHAR(32),
  qty          DECIMAL(20,4),
  tonnage      DECIMAL(20,4),
  amount       DECIMAL(20,2),
  is_on_time   TINYINT,
  src_update_time DATETIME
)
PRIMARY KEY(tenant_id, receipt_id)
PARTITION BY RANGE(receipt_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(receipt_id) BUCKETS 8
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_purchase_daily (
  tenant_id              BIGINT      NOT NULL,
  biz_date               DATE        NOT NULL,
  supplier_id            BIGINT,
  org_id                 BIGINT,
  material_id            BIGINT,
  origin_id              BIGINT,
  grade_code             VARCHAR(32),
  po_count               INT              SUM,
  po_amount              DECIMAL(20,2)    SUM,
  po_tonnage             DECIMAL(20,4)    SUM,
  promise_tonnage        DECIMAL(20,4)    SUM,
  received_tonnage       DECIMAL(20,4)    SUM,
  on_time_receipt_tonnage DECIMAL(20,4)   SUM,
  overdue_po             INT              SUM,
  lead_days              DECIMAL(10,2)    REPLACE
)
AGGREGATE KEY(tenant_id, biz_date, supplier_id, org_id, material_id, origin_id, grade_code)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(supplier_id) BUCKETS 16
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_iqc_daily (
  tenant_id      BIGINT      NOT NULL,
  biz_date       DATE        NOT NULL,
  supplier_id    BIGINT,
  material_id    BIGINT,
  insp_tonnage   DECIMAL(20,4)    SUM,
  pass_tonnage   DECIMAL(20,4)    SUM,
  reject_tonnage DECIMAL(20,4)    SUM
)
AGGREGATE KEY(tenant_id, biz_date, supplier_id, material_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(supplier_id) BUCKETS 8
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_ap_snapshot (
  tenant_id    BIGINT      NOT NULL,
  snap_date    DATE        NOT NULL,
  supplier_id  BIGINT,
  ap_amount    DECIMAL(20,2),
  overdue_amount DECIMAL(20,2),
  src_update_time DATETIME
)
DUPLICATE KEY(tenant_id, snap_date, supplier_id)
PARTITION BY RANGE(snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(supplier_id) BUCKETS 8
PROPERTIES("replication_num"="3");
