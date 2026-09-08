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

  ============= 前端 =============
  指标注册中心:    http://localhost:5173
  AI 经营早报 H5:  http://localhost:5174

  ============= 网关 + 业务 API =============
  Gateway 统一入口: http://localhost:8000  (JWT, 推荐通过它)
    /v1/auth/login (登录拿 JWT, demo 密码=demo)
    /v1/chat/messages (SSE)
    /v1/briefing/today
    /v1/scheduled-reports
    /v1/billing/wallet/{tid}
    /v1/payment/orders
    /api/registry/v1/metrics

  ============= 各服务直接端口 (开发用) =============
  DSL 编译器 API:  http://localhost:8000/docs (注: 与 gateway 端口冲突, 生产 gateway 占 8000)
  报表 CRUD API:   http://localhost:8080
  计费服务 API:    http://localhost:8081
  支付服务 API:    http://localhost:8082
  指标注册后端:    http://localhost:8090
  报表调度器:      http://localhost:8100
  AI 编排器 SSE:   http://localhost:8200
  风控告警:        http://localhost:8300
  预测服务:        http://localhost:8400
  AI 早报后端:     http://localhost:8500
  建议引擎:        http://localhost:8600
  ETL Runner:      http://localhost:8700
  查询引擎:        http://localhost:8800
  数据质量监控:    http://localhost:8900
  RAG/模型路由:    http://localhost:8950

  ============= 监控 (启动 ops/monitoring/docker-compose.monitoring.yml 后) =============
  Prometheus:      http://localhost:9090
  Grafana:         http://localhost:3000  (admin/admin)
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
