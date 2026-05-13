#!/usr/bin/env bash
# 每月 1 号: 把 24 个月前的事实表归档到对象存储 (Iceberg/Parquet)
# 与 ddl/03_inventory.sql 等表的 PARTITION BY RANGE 配合: 直接 DROP 旧分区
set -euo pipefail

ARCHIVE_BEFORE_MONTH="${1:-$(date -d '24 months ago' +%Y-%m-01)}"

echo "归档基准日: $ARCHIVE_BEFORE_MONTH"

TABLES=(
  dwd_sales_order_line dwd_sales_delivery dws_sales_daily
  dws_inv_daily_snapshot dws_inv_movement_daily
  dwd_work_order dwd_equipment_status dws_oee_daily dws_equip_daily
  dwd_purchase_order_line dwd_purchase_receipt
  dwd_quality_inspection dws_quality_daily
)

for t in "${TABLES[@]}"; do
  # 1. 拷贝到对象存储 (Iceberg)
  echo "[archive] $t"
  mysql -h "$SR_HOST" -P 9030 -uroot -e "
    INSERT INTO iceberg_archive.${t}_history
    SELECT * FROM steel_dw.${t}
    WHERE DATE_TRUNC('MONTH', src_update_time) < '$ARCHIVE_BEFORE_MONTH'
  " || true
  # 2. 删除 StarRocks 上的旧分区
  PARTITIONS=$(mysql -h "$SR_HOST" -P 9030 -uroot -N -e "
    SHOW PARTITIONS FROM steel_dw.${t}
  " | awk -v cutoff="$ARCHIVE_BEFORE_MONTH" '$4 < cutoff {print $2}')
  for p in $PARTITIONS; do
    mysql -h "$SR_HOST" -P 9030 -uroot -e "
      ALTER TABLE steel_dw.${t} DROP PARTITION $p
    "
  done
done

echo "归档完成"
