-- =====================================================================
-- 生产/加工 + 质量域
-- =====================================================================
USE steel_dw;

-- ----------------------------- 工单 -----------------------------
CREATE TABLE IF NOT EXISTS dwd_work_order (
  tenant_id        BIGINT       NOT NULL,
  wo_id            BIGINT       NOT NULL,
  wo_no            VARCHAR(64),
  material_id      BIGINT,
  origin_id        BIGINT,
  grade_code       VARCHAR(32),
  workcenter_id    BIGINT,
  process          VARCHAR(32),
  plan_qty         DECIMAL(20,4),
  plan_tonnage     DECIMAL(20,4),
  good_qty         DECIMAL(20,4),
  good_tonnage     DECIMAL(20,4),
  scrap_qty        DECIMAL(20,4),
  scrap_tonnage    DECIMAL(20,4),
  rework_tonnage   DECIMAL(20,4),
  plan_start       DATETIME,
  plan_end         DATETIME,
  actual_start     DATETIME,
  actual_end       DATETIME,
  status           VARCHAR(16),       -- PLANNED / IN_PROGRESS / DONE / CANCELED
  is_overdue       TINYINT,
  src_update_time  DATETIME
)
PRIMARY KEY(tenant_id, wo_id)
PARTITION BY RANGE(plan_start) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(wo_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 设备状态 (来自 OPC-UA/IoT) -----------------------------
CREATE TABLE IF NOT EXISTS dwd_equipment_status (
  tenant_id    BIGINT      NOT NULL,
  equip_id     BIGINT      NOT NULL,
  ts           DATETIME    NOT NULL,
  status       VARCHAR(16),     -- RUN/IDLE/DOWN/CHANGEOVER
  duration_sec INT,
  speed        DECIMAL(20,4)
)
DUPLICATE KEY(tenant_id, equip_id, ts)
PARTITION BY RANGE(ts) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(equip_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- DWS: 工单日 -----------------------------
CREATE TABLE IF NOT EXISTS dws_wo_daily (
  tenant_id      BIGINT      NOT NULL,
  biz_date       DATE        NOT NULL,
  workcenter_id  BIGINT,
  wo_count       INT                SUM,
  completed_wo   INT                SUM,
  overdue_wo     INT                SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- DWS: 生产/加工日 -----------------------------
CREATE TABLE IF NOT EXISTS dws_mill_daily (
  tenant_id     BIGINT       NOT NULL,
  biz_date      DATE         NOT NULL,
  workcenter_id BIGINT,
  process       VARCHAR(32),
  grade_code    VARCHAR(32),
  product_type  VARCHAR(32),
  input_tonnage  DECIMAL(20,4)       SUM,
  output_tonnage DECIMAL(20,4)       SUM,
  good_tonnage   DECIMAL(20,4)       SUM,
  scrap_tonnage  DECIMAL(20,4)       SUM,
  rework_tonnage DECIMAL(20,4)       SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id, process, grade_code, product_type)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 8
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_process_daily (
  tenant_id        BIGINT       NOT NULL,
  biz_date         DATE         NOT NULL,
  workcenter_id    BIGINT,
  process          VARCHAR(32),
  material_id      BIGINT,
  input_tonnage    DECIMAL(20,4)     SUM,
  output_tonnage   DECIMAL(20,4)     SUM,
  net_used_tonnage DECIMAL(20,4)     SUM,
  scrap_tonnage    DECIMAL(20,4)     SUM,
  rework_tonnage   DECIMAL(20,4)     SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id, process, material_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(material_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 计划达成 -----------------------------
CREATE TABLE IF NOT EXISTS dws_plan_daily (
  tenant_id     BIGINT       NOT NULL,
  biz_date      DATE         NOT NULL,
  workcenter_id BIGINT,
  plan_tonnage  DECIMAL(20,4)     SUM,
  actual_tonnage DECIMAL(20,4)    SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- OEE -----------------------------
CREATE TABLE IF NOT EXISTS dws_oee_daily (
  tenant_id            BIGINT       NOT NULL,
  biz_date             DATE         NOT NULL,
  workcenter_id        BIGINT,
  equip_id             BIGINT,
  plan_time_sec        BIGINT             SUM,
  run_time_sec         BIGINT             SUM,
  down_time_sec        BIGINT             SUM,
  changeover_time_sec  BIGINT             SUM,
  total_qty            DECIMAL(20,4)      SUM,
  good_qty             DECIMAL(20,4)      SUM,
  standard_cycle_sec   DECIMAL(20,4)      REPLACE
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id, equip_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(equip_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 设备日 -----------------------------
CREATE TABLE IF NOT EXISTS dws_equip_daily (
  tenant_id          BIGINT       NOT NULL,
  biz_date           DATE         NOT NULL,
  equip_id           BIGINT,
  run_time_sec       BIGINT             SUM,
  down_time_sec      BIGINT             SUM,
  failure_count      INT                SUM,
  changeover_sec     BIGINT             SUM,
  changeover_count   INT                SUM
)
AGGREGATE KEY(tenant_id, biz_date, equip_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(equip_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 能耗 -----------------------------
CREATE TABLE IF NOT EXISTS dws_energy_daily (
  tenant_id     BIGINT       NOT NULL,
  biz_date      DATE         NOT NULL,
  workcenter_id BIGINT,
  kgce          DECIMAL(20,4)     SUM,
  kwh           DECIMAL(20,4)     SUM,
  water_ton     DECIMAL(20,4)     SUM,
  gas_m3        DECIMAL(20,4)     SUM,
  output_tonnage DECIMAL(20,4)    SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 成本 -----------------------------
CREATE TABLE IF NOT EXISTS dws_cost_daily (
  tenant_id      BIGINT       NOT NULL,
  biz_date       DATE         NOT NULL,
  workcenter_id  BIGINT,
  material_cost  DECIMAL(20,2)     SUM,
  labor_cost     DECIMAL(20,2)     SUM,
  energy_cost    DECIMAL(20,2)     SUM,
  overhead_cost  DECIMAL(20,2)     SUM,
  total_cost     DECIMAL(20,2)     SUM,
  output_tonnage DECIMAL(20,4)     SUM
)
AGGREGATE KEY(tenant_id, biz_date, workcenter_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ============================================================
-- 质量域
-- ============================================================

CREATE TABLE IF NOT EXISTS dwd_quality_inspection (
  tenant_id       BIGINT      NOT NULL,
  insp_id         BIGINT      NOT NULL,
  insp_date       DATE,
  source          VARCHAR(16),     -- IQC/IPQC/FQC/OQC
  category        VARCHAR(16),     -- SURFACE/DIM/MECH/CHEM
  material_id     BIGINT,
  origin_id       BIGINT,
  grade_code      VARCHAR(32),
  supplier_id     BIGINT,
  wo_id           BIGINT,
  workcenter_id   BIGINT,
  defect_id       BIGINT,
  total_qty       DECIMAL(20,4),
  defect_qty      DECIMAL(20,4),
  defect_tonnage  DECIMAL(20,4),
  pass            TINYINT,
  downgrade_tonnage DECIMAL(20,4),
  src_update_time DATETIME
)
PRIMARY KEY(tenant_id, insp_id)
PARTITION BY RANGE(insp_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(insp_id) BUCKETS 16
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_quality_daily (
  tenant_id            BIGINT      NOT NULL,
  biz_date             DATE        NOT NULL,
  source               VARCHAR(16),
  category             VARCHAR(16),
  workcenter_id        BIGINT,
  origin_id            BIGINT,
  grade_code           VARCHAR(32),
  insp_tonnage         DECIMAL(20,4)    SUM,
  pass_tonnage         DECIMAL(20,4)    SUM,
  defect_tonnage       DECIMAL(20,4)    SUM,
  downgrade_tonnage    DECIMAL(20,4)    SUM,
  dim_oos_tonnage      DECIMAL(20,4)    SUM,
  total_qty            DECIMAL(20,4)    SUM,
  defect_qty           DECIMAL(20,4)    SUM,
  test_count           INT              SUM,
  pass_count           INT              SUM,
  actual_weight        DECIMAL(20,4)    SUM,
  theoretical_weight   DECIMAL(20,4)    SUM,
  rework_cost          DECIMAL(20,2)    SUM,
  scrap_cost           DECIMAL(20,2)    SUM,
  complaint_cost       DECIMAL(20,2)    SUM
)
AGGREGATE KEY(tenant_id, biz_date, source, category, workcenter_id, origin_id, grade_code)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(grade_code) BUCKETS 4
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dws_complaint_daily (
  tenant_id           BIGINT      NOT NULL,
  biz_date            DATE        NOT NULL,
  customer_id         BIGINT,
  complaint_count     INT              SUM,
  closed_on_time      INT              SUM,
  delivered_orders    INT              SUM
)
AGGREGATE KEY(tenant_id, biz_date, customer_id)
PARTITION BY RANGE(biz_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 4
PROPERTIES("replication_num"="3");
