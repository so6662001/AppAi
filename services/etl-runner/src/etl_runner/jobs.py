"""ETL 任务定义."""
from __future__ import annotations
import logging
import os
from datetime import date, timedelta
from typing import Callable


log = logging.getLogger("etl.jobs")

SR_HOST = os.environ.get("SR_HOST", "localhost")
SR_PORT = int(os.environ.get("SR_PORT", 9030))
SR_USER = os.environ.get("SR_USER", "root")
SR_PASS = os.environ.get("SR_PASS", "")
SR_DB   = os.environ.get("SR_DB", "steel_dw")


def _conn():
    import pymysql
    return pymysql.connect(host=SR_HOST, port=SR_PORT, user=SR_USER,
                           password=SR_PASS, db=SR_DB, charset="utf8mb4",
                           connect_timeout=3)


def inv_daily_snapshot(snap_date: date | None = None) -> int:
    """物化昨日 dws_inv_daily_snapshot. 即使无变动也写, 保证跨日 AVG 正确."""
    snap_date = snap_date or (date.today() - timedelta(days=1))
    sql = f"""
INSERT INTO dws_inv_daily_snapshot
    (tenant_id, snap_date, org_id, warehouse_id, warehouse_type,
     material_id, origin_id, grade_code, product_type,
     on_hand_qty, on_hand_tonnage, coil_count, amount, avg_cost_price,
     aging_days, aging_0_30, aging_31_90, aging_91_180,
     aging_181_365, aging_365_plus, last_move_days,
     safety_stock, demand_30d, src_update_time)
SELECT
  ib.tenant_id, '{snap_date.isoformat()}' AS snap_date,
  COALESCE(w.org_id, 0) AS org_id, ib.warehouse_id, ib.warehouse_type,
  ib.material_id, ib.origin_id, ib.grade_code,
  m.product_type AS product_type,
  SUM(ib.on_hand_qty),
  SUM(ib.on_hand_tonnage),
  COUNT(DISTINCT ib.coil_no),
  SUM(ib.amount),
  AVG(ib.unit_cost) AS avg_cost_price,
  DATEDIFF('{snap_date.isoformat()}', MIN(ib.last_in_date)) AS aging_days,
  SUM(CASE WHEN DATEDIFF('{snap_date.isoformat()}', ib.last_in_date) BETWEEN 0 AND 30   THEN ib.amount ELSE 0 END) AS aging_0_30,
  SUM(CASE WHEN DATEDIFF('{snap_date.isoformat()}', ib.last_in_date) BETWEEN 31 AND 90  THEN ib.amount ELSE 0 END) AS aging_31_90,
  SUM(CASE WHEN DATEDIFF('{snap_date.isoformat()}', ib.last_in_date) BETWEEN 91 AND 180 THEN ib.amount ELSE 0 END) AS aging_91_180,
  SUM(CASE WHEN DATEDIFF('{snap_date.isoformat()}', ib.last_in_date) BETWEEN 181 AND 365 THEN ib.amount ELSE 0 END) AS aging_181_365,
  SUM(CASE WHEN DATEDIFF('{snap_date.isoformat()}', ib.last_in_date) > 365              THEN ib.amount ELSE 0 END) AS aging_365_plus,
  DATEDIFF('{snap_date.isoformat()}', MAX(ib.last_move_date)) AS last_move_days,
  NULL AS safety_stock,
  NULL AS demand_30d,
  NOW()
FROM dwd_inv_balance ib
LEFT JOIN dim_warehouse    w ON w.tenant_id = ib.tenant_id AND w.warehouse_id = ib.warehouse_id
LEFT JOIN dim_material_his m ON m.tenant_id = ib.tenant_id AND m.material_id  = ib.material_id AND m.is_current = 1
GROUP BY ib.tenant_id, ib.warehouse_id, ib.warehouse_type,
         ib.material_id, ib.origin_id, ib.grade_code, m.product_type, org_id
    """
    try:
        conn = _conn()
        try:
            with conn.cursor() as cur:
                rc = cur.execute(sql)
            conn.commit()
            log.info("inv_daily_snapshot %s rows=%s", snap_date, rc)
            return rc or 0
        finally:
            conn.close()
    except Exception as e:
        log.warning("inv_daily_snapshot failed (will retry next time): %s", e)
        return 0


def dws_sales_daily(biz_date: date | None = None) -> int:
    """重算昨日 dws_sales_daily (实际是 ETL 链路上游做; 这里给容错入口)."""
    biz_date = biz_date or (date.today() - timedelta(days=1))
    log.info("dws_sales_daily %s (placeholder, normally driven by SeaTunnel)", biz_date)
    return 0


JOBS: dict[str, Callable[[], int]] = {
    "inv_daily_snapshot": inv_daily_snapshot,
    "dws_sales_daily": dws_sales_daily,
}
