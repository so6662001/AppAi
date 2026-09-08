#!/usr/bin/env bash
# 检查依赖工具是否齐全
set -e

check() {
  local name=$1 cmd=$2 hint=$3
  if command -v "$cmd" >/dev/null 2>&1; then
    local ver
    ver=$("$cmd" --version 2>&1 | head -1)
    printf "  \033[32m✓\033[0m %-16s %s\n" "$name" "$ver"
  else
    printf "  \033[31m✗\033[0m %-16s 缺失. 安装: %s\n" "$name" "$hint"
  fi
}

echo "== 钢铁 AI 经营分析平台 · 环境检查 =="
check "Git"            git           "apt install git"
check "Docker"         docker        "https://docs.docker.com/engine/install/"
check "Compose"        "docker"      "随 Docker 安装 (docker compose version)"
check "Node.js"        node          "nvm install 18"
check "npm"            npm           "随 Node.js"
check "Python 3"       python3       "apt install python3 python3-pip"
check "pip"            pip3          "apt install python3-pip"
check "Java"           java          "apt install openjdk-17-jdk"
check "curl"           curl          "apt install curl"
check "redis-cli (可选)" redis-cli   "apt install redis-tools"

echo
echo "== 端口占用检查 =="
for port in 3306 5173 5174 6379 8000 8030 9030; do
  if (echo > /dev/tcp/127.0.0.1/$port) 2>/dev/null; then
    echo "  ✗ 端口 $port 已被占用"
  else
    echo "  ✓ 端口 $port 可用"
  fi
done

echo
echo "== 硬件资源 =="
echo "  CPU: $(nproc) 核"
echo "  内存: $(free -h | awk '/Mem:/ {print $2}')"
echo "  磁盘: $(df -h / | awk 'NR==2 {print $4}') 可用"

echo
echo "== Docker 镜像预检 (可选, 提前 pull) =="
echo "  docker pull starrocks/allin1-ubuntu:3.2-latest"
echo "  docker pull mysql:8.0"
echo "  docker pull redis:7-alpine"
echo "  docker pull node:20-alpine"
