#!/usr/bin/env bash
# 启动 uniapp H5 并允许局域网/外网访问 (用于真机扫码试用)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/apps/uniapp-briefing"

if [ ! -d node_modules ]; then
  echo "首次运行, 安装依赖..."
  npm install
fi

# 找本机第一个非 127 IP
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo localhost)

echo
echo "============================================"
echo "  H5 已绑定到 0.0.0.0:5174"
echo "  本机访问:   http://localhost:5174"
echo "  局域网访问: http://$IP:5174"
echo
echo "  扫码方式:"
echo "  1. 手机连同一 WiFi, 浏览器输入上述 URL"
echo "  2. 微信扫一扫 → 生成二维码"
echo "  3. 或用 ngrok/cpolar 暴露公网域名"
echo "============================================"
echo

exec npx vite --host 0.0.0.0 --port 5174
