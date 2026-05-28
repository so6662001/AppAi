-- =====================================================================
-- 期现结合: 锁价/点价订单 + 套保头寸 + 基差/敞口
-- 适用: 启用 ENABLE_HEDGE 的租户 (钢贸+钢厂常见)
-- =====================================================================
USE steel_dw;

-- ----------------------------- 锁价订单 (客户跟我方锁定一口价, 我方对外套保) -----------------------------
CREATE TABLE IF NOT EXISTS fact_locked_price_order (
  tenant_id        BIGINT       NOT NULL,
  entity_id        BIGINT,
  order_date       DATE         NOT NULL,
  order_no         VARCHAR(64)  NOT NULL,
  customer_id      BIGINT,
  rep_id           BIGINT,
  material_id      BIGINT,
  product_type     VARCHAR(32),
  grade_code       VARCHAR(32),
  origin_id        BIGINT,
  lock_price       DECIMAL(12,4),               -- 客户锁定的现货价 (元/吨, 含税)
  lock_tonnage     DECIMAL(20,4),
  delivery_date    DATE,                        -- 约定提货日
  fixed_at         DATETIME,                    -- 锁价时点
  -- 对冲信息
  hedge_contract   VARCHAR(16),                 -- RB/HC/I/JM/SS
  hedge_position_id VARCHAR(64),                -- 关联期货头寸编号
  hedge_open_price DECIMAL(12,4),               -- 同时开的期货价
  -- 状态
  status           VARCHAR(16),                 -- LOCKED/PARTIAL_DELIVERED/CLOSED/CANCELLED
  delivered_tonnage DECIMAL(20,4) DEFAULT 0,
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, order_date, order_no)
PARTITION BY RANGE (order_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(order_no) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 点价订单 (基差合同, 客户在窗口期内选择某日盘价点价) -----------------------------
CREATE TABLE IF NOT EXISTS fact_spot_price_order (
  tenant_id        BIGINT       NOT NULL,
  entity_id        BIGINT,
  order_date       DATE         NOT NULL,
  order_no         VARCHAR(64)  NOT NULL,
  customer_id      BIGINT,
  rep_id           BIGINT,
  material_id      BIGINT,
  product_type     VARCHAR(32),
  grade_code       VARCHAR(32),
  origin_id        BIGINT,
  hedge_contract   VARCHAR(16)  NOT NULL,        -- 基准期货合约
  basis            DECIMAL(12,4),                -- 约定基差 (现货 = 期货价 + basis)
  total_tonnage    DECIMAL(20,4),
  picked_tonnage   DECIMAL(20,4) DEFAULT 0,      -- 已点价吨数
  pick_window_start DATE,
  pick_window_end   DATE,
  default_pick_price DECIMAL(12,4),              -- 兜底点价 (窗口期到了未点)
  status           VARCHAR(16),                  -- OPEN/PARTIAL_PICKED/FULL_PICKED/EXPIRED
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, order_date, order_no)
PARTITION BY RANGE (order_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(order_no) BUCKETS 8
PROPERTIES("replication_num"="3");

-- 点价明细 (一张点价单可分批点价)
CREATE TABLE IF NOT EXISTS fact_spot_price_pick (
  tenant_id        BIGINT       NOT NULL,
  entity_id        BIGINT,
  pick_date        DATE         NOT NULL,
  order_no         VARCHAR(64),
  pick_seq         INT,
  pick_tonnage     DECIMAL(20,4),
  futures_price    DECIMAL(12,4),
  basis_at_pick    DECIMAL(12,4),
  effective_price  DECIMAL(12,4),               -- = futures_price + basis_at_pick
  operator_id      BIGINT,
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, pick_date, order_no, pick_seq)
DISTRIBUTED BY HASH(order_no) BUCKETS 8
PROPERTIES("replication_num"="3");

-- ----------------------------- 套保头寸日明细 (扩展原 dws_hedge_position_daily) -----------------------------
-- 注: 原 03_inventory.sql 已建一张更粗粒度的 dws_hedge_position_daily,
-- 此处建一张按 entity + 合约月 + 多空方向 的细粒度表, 用于 PnL 拆分
CREATE TABLE IF NOT EXISTS dws_hedge_position_detail_daily (
  tenant_id          BIGINT       NOT NULL,
  snap_date          DATE         NOT NULL,
  entity_id          BIGINT,
  hedge_contract     VARCHAR(16)  NOT NULL,         -- RB/HC/I/JM/SS
  contract_month     VARCHAR(8),                    -- 2026-10
  direction          VARCHAR(8),                    -- LONG/SHORT
  open_position      DECIMAL(20,4),
  close_position     DECIMAL(20,4),
  net_position_tons  DECIMAL(20,4),                 -- 净持仓吨数
  net_position_amt   DECIMAL(20,2),
  market_price       DECIMAL(12,4),
  realized_pnl_day   DECIMAL(20,2),
  unrealized_pnl_day DECIMAL(20,2),
  margin_occupied    DECIMAL(20,2),
  src_update_time    DATETIME
)
DUPLICATE KEY (tenant_id, snap_date, entity_id, hedge_contract, contract_month, direction)
PARTITION BY RANGE (snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(hedge_contract) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 基差日明细 -----------------------------
CREATE TABLE IF NOT EXISTS dws_basis_daily (
  tenant_id        BIGINT       NOT NULL,
  snap_date        DATE         NOT NULL,
  grade_code       VARCHAR(32),
  product_type     VARCHAR(32),
  region           VARCHAR(32),
  hedge_contract   VARCHAR(16),
  spot_price       DECIMAL(12,4),
  futures_price    DECIMAL(12,4),
  basis            DECIMAL(12,4),               -- spot - futures
  basis_rate       DECIMAL(8,6),                -- basis / spot
  warn_level       VARCHAR(8),                  -- NORMAL/WIDE/INVERT (基差走宽/倒挂)
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, snap_date, grade_code, product_type, region, hedge_contract)
PARTITION BY RANGE (snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(grade_code, product_type) BUCKETS 4
PROPERTIES("replication_num"="3");

-- ----------------------------- 套保 PnL 拆分日表 -----------------------------
CREATE TABLE IF NOT EXISTS dws_hedge_pnl_split_daily (
  tenant_id        BIGINT       NOT NULL,
  snap_date        DATE         NOT NULL,
  entity_id        BIGINT,
  spot_pnl         DECIMAL(20,2),                -- 现货段毛利
  futures_pnl      DECIMAL(20,2),                -- 期货段盈亏
  basis_pnl        DECIMAL(20,2),                -- 基差变化贡献
  combined_pnl     DECIMAL(20,2),                -- 总
  combined_margin_pct DECIMAL(8,6),
  src_update_time  DATETIME
)
DUPLICATE KEY (tenant_id, snap_date, entity_id)
PARTITION BY RANGE (snap_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(entity_id) BUCKETS 4
PROPERTIES("replication_num"="3");
