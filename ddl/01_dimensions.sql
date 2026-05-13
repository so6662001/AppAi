-- =====================================================================
-- 共享维度表 (dim_*)
-- 采用 Primary Key 模型, 支持上游变更的 upsert
-- 慢变维(客户/物料/供应商) 用 _his 拉链表
-- =====================================================================
USE steel_dw;

-- ----------------------------- 日期维 -----------------------------
CREATE TABLE IF NOT EXISTS dim_date (
  date_key      DATE        NOT NULL,
  year          INT,
  quarter       INT,
  month         INT,
  week          INT,
  day           INT,
  ym            VARCHAR(7),
  yq            VARCHAR(7),
  is_workday    TINYINT,
  is_holiday    TINYINT,
  fiscal_year   INT,
  fiscal_period INT
)
PRIMARY KEY(date_key)
DISTRIBUTED BY HASH(date_key) BUCKETS 1
PROPERTIES("replication_num"="3");

-- ----------------------------- 组织维 -----------------------------
CREATE TABLE IF NOT EXISTS dim_org (
  tenant_id     BIGINT      NOT NULL,
  org_id        BIGINT      NOT NULL,
  org_code      VARCHAR(64),
  org_name      VARCHAR(128),
  parent_id     BIGINT,
  org_path      VARCHAR(512),
  org_level     INT,
  region        VARCHAR(64),
  branch        VARCHAR(64),
  is_active     TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, org_id)
DISTRIBUTED BY HASH(org_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 产地维 (新增) -----------------------------
CREATE TABLE IF NOT EXISTS dim_origin (
  tenant_id        BIGINT       NOT NULL,
  origin_id        BIGINT       NOT NULL,
  origin_code      VARCHAR(32),
  origin_name      VARCHAR(64),    -- 沙钢/永钢/鞍钢/宝钢/河钢/马钢/日照/莱钢/包钢/首钢…
  origin_group     VARCHAR(32),    -- 沙钢系/宝武系/鞍钢系/河钢系/民营/进口
  origin_region    VARCHAR(32),    -- 华东/华北/华南/东北/西南/进口
  origin_country   VARCHAR(16),
  mill_tier        VARCHAR(8),     -- T1/T2/T3
  preferred_premium DECIMAL(10,2), -- 合理溢价(元/吨), 偏离报警
  is_active        TINYINT,
  etl_load_time    DATETIME
)
PRIMARY KEY(tenant_id, origin_id)
DISTRIBUTED BY HASH(origin_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 材质维 (新增) -----------------------------
CREATE TABLE IF NOT EXISTS dim_grade (
  tenant_id        BIGINT      NOT NULL,
  grade_code       VARCHAR(32) NOT NULL, -- Q235B/Q355B/SPCC/DC01/304/316L…
  grade_name       VARCHAR(64),
  grade_family     VARCHAR(16),          -- 碳结/低合金/不锈/优特钢/工模具
  grade_standard   VARCHAR(16),          -- GB/JIS/ASTM/EN
  is_alloy         TINYINT,
  is_stainless     TINYINT,
  yield_strength   DECIMAL(10,2),        -- MPa
  tensile_strength DECIMAL(10,2),
  is_active        TINYINT,
  etl_load_time    DATETIME
)
PRIMARY KEY(tenant_id, grade_code)
DISTRIBUTED BY HASH(grade_code) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 客户维 (拉链) -----------------------------
CREATE TABLE IF NOT EXISTS dim_customer_his (
  tenant_id      BIGINT      NOT NULL,
  customer_sk    BIGINT      NOT NULL,    -- 代理键
  customer_id    BIGINT,
  customer_code  VARCHAR(64),
  customer_name  VARCHAR(256),
  industry       VARCHAR(64),
  region         VARCHAR(64),
  sales_owner_id BIGINT,
  level          VARCHAR(8),               -- A/B/C
  risk_grade     VARCHAR(8),
  payment_terms_days INT,
  start_date     DATE,
  end_date       DATE,
  is_current     TINYINT,
  etl_load_time  DATETIME
)
PRIMARY KEY(tenant_id, customer_sk)
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
PROPERTIES("replication_num"="3");

-- ----------------------------- 物料维 (拉链, 含产地材质) -----------------------------
CREATE TABLE IF NOT EXISTS dim_material_his (
  tenant_id     BIGINT       NOT NULL,
  material_sk   BIGINT       NOT NULL,
  material_id   BIGINT,
  material_code VARCHAR(64),
  material_name VARCHAR(256),
  product_type  VARCHAR(32),
  grade_code    VARCHAR(32),       -- 冗余材质便于切片
  spec_thk      DECIMAL(10,3),
  spec_wid      DECIMAL(10,2),
  spec_len      DECIMAL(10,2),
  surface_treat VARCHAR(32),       -- 酸洗/镀锌/镀铝锌/彩涂/裸卷
  origin_id     BIGINT,            -- 产地
  unit          VARCHAR(8),
  abc_class     VARCHAR(2),
  start_date    DATE,
  end_date      DATE,
  is_current    TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, material_sk)
DISTRIBUTED BY HASH(material_id) BUCKETS 32
PROPERTIES("replication_num"="3");

-- ----------------------------- 供应商维 (拉链) -----------------------------
CREATE TABLE IF NOT EXISTS dim_supplier_his (
  tenant_id     BIGINT      NOT NULL,
  supplier_sk   BIGINT      NOT NULL,
  supplier_id   BIGINT,
  supplier_code VARCHAR(64),
  supplier_name VARCHAR(256),
  region        VARCHAR(64),
  level         VARCHAR(8),
  start_date    DATE,
  end_date      DATE,
  is_current    TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, supplier_sk)
DISTRIBUTED BY HASH(supplier_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 仓库维 -----------------------------
CREATE TABLE IF NOT EXISTS dim_warehouse (
  tenant_id      BIGINT      NOT NULL,
  warehouse_id   BIGINT      NOT NULL,
  warehouse_code VARCHAR(64),
  warehouse_name VARCHAR(128),
  warehouse_type VARCHAR(16),     -- 自有/寄售/保税/客户仓/第三方
  region         VARCHAR(64),
  total_area     DECIMAL(12,2),
  is_active      TINYINT,
  etl_load_time  DATETIME
)
PRIMARY KEY(tenant_id, warehouse_id)
DISTRIBUTED BY HASH(warehouse_id) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 工作中心 / 设备 -----------------------------
CREATE TABLE IF NOT EXISTS dim_workcenter (
  tenant_id       BIGINT      NOT NULL,
  workcenter_id   BIGINT      NOT NULL,
  workcenter_code VARCHAR(64),
  workcenter_name VARCHAR(128),
  process         VARCHAR(32),     -- 高炉/转炉/连铸/热轧/冷轧/镀锌/酸洗/剪切/开平/纵剪
  line_no         VARCHAR(32),
  is_active       TINYINT,
  etl_load_time   DATETIME
)
PRIMARY KEY(tenant_id, workcenter_id)
DISTRIBUTED BY HASH(workcenter_id) BUCKETS 4
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dim_equipment (
  tenant_id     BIGINT      NOT NULL,
  equip_id      BIGINT      NOT NULL,
  equip_code    VARCHAR(64),
  equip_name    VARCHAR(128),
  workcenter_id BIGINT,
  equip_type    VARCHAR(32),
  is_active     TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, equip_id)
DISTRIBUTED BY HASH(equip_id) BUCKETS 4
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dim_employee (
  tenant_id     BIGINT      NOT NULL,
  employee_id   BIGINT      NOT NULL,
  employee_code VARCHAR(64),
  employee_name VARCHAR(128),
  dept_id       BIGINT,
  role          VARCHAR(64),
  manager_id    BIGINT,
  is_active     TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, employee_id)
DISTRIBUTED BY HASH(employee_id) BUCKETS 4
PROPERTIES("replication_num"="3");

CREATE TABLE IF NOT EXISTS dim_defect (
  tenant_id   BIGINT      NOT NULL,
  defect_id   BIGINT      NOT NULL,
  defect_code VARCHAR(64),
  defect_name VARCHAR(128),
  category    VARCHAR(32),     -- SURFACE/DIM/MECH/CHEM
  is_active   TINYINT,
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, defect_id)
DISTRIBUTED BY HASH(defect_id) BUCKETS 2
PROPERTIES("replication_num"="3");

-- ----------------------------- 客户授信维 -----------------------------
CREATE TABLE IF NOT EXISTS dim_customer_credit (
  tenant_id           BIGINT      NOT NULL,
  customer_id         BIGINT      NOT NULL,
  effective_from      DATE        NOT NULL,
  effective_to        DATE,
  credit_limit        DECIMAL(20,2),
  ar_limit            DECIMAL(20,2),
  payment_terms_days  INT,
  collateral          DECIMAL(20,2),
  risk_grade          VARCHAR(8),
  etl_load_time       DATETIME
)
PRIMARY KEY(tenant_id, customer_id, effective_from)
DISTRIBUTED BY HASH(customer_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 期间费用分摊规则 -----------------------------
CREATE TABLE IF NOT EXISTS dim_expense_alloc_rule (
  tenant_id      BIGINT      NOT NULL,
  rule_id        BIGINT      NOT NULL,
  expense_type   VARCHAR(32),     -- SELLING / ADMIN / FINANCE
  alloc_basis    VARCHAR(16),     -- TONNAGE / AMOUNT / GROSS_PROFIT / HEADCOUNT
  scope_org_id   BIGINT,
  effective_from DATE,
  effective_to   DATE,
  is_active      TINYINT,
  etl_load_time  DATETIME
)
PRIMARY KEY(tenant_id, rule_id)
DISTRIBUTED BY HASH(rule_id) BUCKETS 1
PROPERTIES("replication_num"="3");

-- ----------------------------- 钢材指数 -----------------------------
CREATE TABLE IF NOT EXISTS dim_steel_index (
  tenant_id    BIGINT       NOT NULL,
  price_date   DATE         NOT NULL,
  grade_code   VARCHAR(32)  NOT NULL,
  product_type VARCHAR(32)  NOT NULL,
  region       VARCHAR(32)  NOT NULL,
  idx_price    DECIMAL(12,2),
  source       VARCHAR(32),         -- Mysteel/SMM/上海期货
  etl_load_time DATETIME
)
PRIMARY KEY(tenant_id, price_date, grade_code, product_type, region)
PARTITION BY RANGE(price_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(grade_code) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 挂牌价 (新增, 每日) -----------------------------
CREATE TABLE IF NOT EXISTS dim_price_list_daily (
  tenant_id    BIGINT       NOT NULL,
  price_date   DATE         NOT NULL,
  origin_id    BIGINT       NOT NULL,
  grade_code   VARCHAR(32)  NOT NULL,
  spec_thk     DECIMAL(10,3) NOT NULL,
  spec_wid     DECIMAL(10,2) NOT NULL,
  product_type VARCHAR(32)  NOT NULL,
  listed_price DECIMAL(12,2),    -- 挂牌价(元/吨, 含税)
  cost_basis   DECIMAL(12,2),    -- 当日成本基准
  index_price  DECIMAL(12,2),    -- 当日 Mysteel 指数
  premium      DECIMAL(12,2),    -- 挂价对指数溢价
  src_update_time DATETIME,
  etl_load_time   DATETIME
)
PRIMARY KEY(tenant_id, price_date, origin_id, grade_code, spec_thk, spec_wid, product_type)
PARTITION BY RANGE(price_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(origin_id, grade_code) BUCKETS 8
PROPERTIES("replication_num"="3");
