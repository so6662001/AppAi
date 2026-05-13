-- =====================================================================
-- StarRocks 异步物化视图 (加速高频查询; DSL 编译器自动路由)
-- =====================================================================
USE steel_dw;

-- ----------------------------- 销售: 月度组织级 -----------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_sales_monthly_org
REFRESH ASYNC EVERY (INTERVAL 1 HOUR)
PARTITION BY date_trunc('month', biz_date)
DISTRIBUTED BY HASH(org_id) BUCKETS 8
AS
SELECT
  tenant_id,
  date_trunc('month', biz_date) AS biz_month,
  org_id,
  origin_id,
  grade_code,
  product_type,
  SUM(order_amount)              AS order_amount,
  SUM(order_tonnage)             AS order_tonnage,
  SUM(gross_profit)              AS gross_profit,
  SUM(delivered_amount)          AS delivered_amount,
  SUM(delivered_tonnage)         AS delivered_tonnage,
  SUM(on_time_tonnage)           AS on_time_tonnage,
  SUM(promise_tonnage)           AS promise_tonnage,
  SUM(cost_amount)               AS cost_amount
FROM dws_sales_daily
GROUP BY 1, 2, 3, 4, 5, 6;

-- ----------------------------- 库存: 月末日均 / 月末快照 -----------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_inventory_monthly
REFRESH ASYNC EVERY (INTERVAL 1 HOUR)
PARTITION BY date_trunc('month', snap_date)
DISTRIBUTED BY HASH(material_id) BUCKETS 16
AS
WITH daily AS (
  SELECT tenant_id, snap_date, org_id, warehouse_id, material_id, origin_id, grade_code,
         SUM(on_hand_tonnage) AS day_ton, SUM(amount) AS day_amt
  FROM dws_inv_daily_snapshot
  GROUP BY 1,2,3,4,5,6,7
)
SELECT
  tenant_id,
  date_trunc('month', snap_date) AS biz_month,
  org_id, warehouse_id, material_id, origin_id, grade_code,
  AVG(day_ton) AS avg_inv_tonnage,
  AVG(day_amt) AS avg_inv_amount,
  MAX_BY(day_ton, snap_date) AS period_end_tonnage,
  MAX_BY(day_amt, snap_date) AS period_end_amount,
  MIN_BY(day_ton, snap_date) AS period_begin_tonnage
FROM daily
GROUP BY 1,2,3,4,5,6,7;

-- ----------------------------- 客户级日宽 (含资金) -----------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_customer_kpi_daily
REFRESH ASYNC EVERY (INTERVAL 1 HOUR)
PARTITION BY biz_date
DISTRIBUTED BY HASH(customer_id) BUCKETS 16
AS
SELECT
  s.tenant_id, s.biz_date, s.customer_id, s.org_id,
  SUM(s.order_amount)                 AS order_amount,
  SUM(s.order_tonnage)                AS order_tonnage,
  SUM(s.gross_profit)                 AS gross_profit,
  AVG(cap.capital_occupation)         AS avg_capital_occupation,
  SUM(cap.capital_occupation * cap.funding_rate / 365) AS capital_cost
FROM dws_sales_daily s
LEFT JOIN dws_customer_capital_daily cap
  ON cap.tenant_id = s.tenant_id
 AND cap.snap_date = s.biz_date
 AND cap.customer_id = s.customer_id
GROUP BY 1,2,3,4;
