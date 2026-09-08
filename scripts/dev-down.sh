#!/usr/bin/env bash
# 关闭开发环境
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

case "${1:-stop}" in
  stop)
    docker compose -f docker-compose.dev.yml stop
    echo "已停止. 重新启动: bash scripts/dev-up.sh"
    ;;
  down)
    docker compose -f docker-compose.dev.yml down
    echo "容器已删除. 数据卷保留. 完全清空请加 --purge"
    ;;
  purge)
    docker compose -f docker-compose.dev.yml down -v
    echo "容器与数据卷均已清空"
    ;;
  *)
    echo "Usage: $0 [stop|down|purge]"
    exit 1
    ;;
esac
