#!/usr/bin/env bash
# 一键启动开发环境
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== 启动 Docker Compose 服务 =="
docker compose -f docker-compose.dev.yml up -d

echo
echo "== 等待 MySQL/Redis/StarRocks 就绪 =="
for svc in mysql redis starrocks; do
  printf "  %-12s " "$svc"
  for i in $(seq 1 60); do
    if docker compose -f docker-compose.dev.yml ps "$svc" | grep -q "healthy\|Up"; then
      echo "OK"
      break
    fi
    printf "."
    sleep 2
  done
done

echo
echo "== 初始化 StarRocks 数据仓库 =="
if docker exec steel-starrocks mysql -h127.0.0.1 -P9030 -uroot \
   -e "SHOW DATABASES;" 2>/dev/null | grep -q steel_dw; then
  echo "  steel_dw 已存在, 跳过建表"
else
  for f in ddl/00_database.sql ddl/01_dimensions.sql ddl/02_sales.sql \
           ddl/03_inventory.sql ddl/04_production_quality.sql \
           ddl/05_procurement.sql ddl/06_capital_risk_forecast_abc.sql \
           ddl/10_materialized_views.sql; do
    echo "  应用 $f"
    docker exec -i steel-starrocks mysql -h127.0.0.1 -P9030 -uroot < "$f" || true
  done
fi

echo
echo "== 加载 Lua 脚本到 Redis =="
for f in services/billing-lua/preauth.lua services/billing-lua/settle.lua \
         services/billing-lua/release.lua services/billing-lua/refund.lua; do
  sha=$(docker exec -i steel-redis redis-cli SCRIPT LOAD "$(cat "$f")" 2>/dev/null || echo "")
  name=$(basename "$f" .lua)
  echo "  $name → $sha"
done

echo
echo "== 服务地址 =="
cat <<EOF

  指标注册中心:    http://localhost:5173
  AI 经营早报 H5:  http://localhost:5174
  DSL 编译器 API:  http://localhost:8000/docs
  报表调度器 API:  http://localhost:8100/health
  StarRocks MySQL: localhost:9030 (root, 无密码)
  StarRocks HTTP:  http://localhost:8030
  MySQL:           localhost:3306 (root / steeldev)
  Redis:           localhost:6379

试一下:
  curl -X POST http://localhost:8000/v1/dsl/compile \\
    -H 'Content-Type: application/json' -d '{
      "dsl": {"metrics":["sales_amount"],"time":{"preset":"yesterday"}},
      "context": {"tenant_id":1,"user_id":1,"business_line":"TRADE"}
    }'

关闭: bash scripts/dev-down.sh
EOF
