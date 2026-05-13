#!/usr/bin/env bash
# 每日 03:00: MySQL 全量备份到对象存储, StarRocks 异地容灾
set -euo pipefail

DATE=$(date +%Y-%m-%d)
BACKUP_DIR="/var/backups/steel-ai/$DATE"
OSS_BUCKET="${OSS_BUCKET:-oss://steel-ai-backup}"

mkdir -p "$BACKUP_DIR"

echo "=== 1. MySQL 全量备份 ==="
for db in steel_chat steel_billing steel_governance; do
  mysqldump --single-transaction --routines --triggers \
    -h "$MYSQL_HOST" -P 3306 -uroot -p"$MYSQL_ROOT_PASSWORD" \
    "$db" | gzip > "$BACKUP_DIR/$db.sql.gz"
done

echo "=== 2. StarRocks 异地容灾 ==="
# StarRocks BACKUP 命令到 HDFS / S3
mysql -h "$SR_FE" -P 9030 -uroot -e "
  BACKUP SNAPSHOT steel_dw_$DATE
  TO repo_oss
  ON ($(echo $SR_BACKUP_TABLES))
"

echo "=== 3. 上传到 OSS ==="
ossutil cp -rf "$BACKUP_DIR" "$OSS_BUCKET/$DATE/"

echo "=== 4. 清理本地 7 天前 ==="
find /var/backups/steel-ai -type d -mtime +7 -exec rm -rf {} +

echo "备份完成: $OSS_BUCKET/$DATE/"
