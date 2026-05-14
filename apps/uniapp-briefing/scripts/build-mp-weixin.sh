#!/usr/bin/env bash
# uniapp 微信小程序打包脚本 - 用于 CI 自动构建
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== 1. 安装依赖 ==="
npm install --no-audit --no-fund

echo "=== 2. 构建微信小程序代码 ==="
npm run build:mp-weixin

OUT_DIR="$ROOT/dist/build/mp-weixin"
if [ ! -d "$OUT_DIR" ]; then
  echo "构建失败, 找不到 $OUT_DIR"
  exit 1
fi

echo "=== 3. 计算大小 ==="
du -sh "$OUT_DIR"
echo "主包文件数: $(find "$OUT_DIR" -maxdepth 1 -type f | wc -l)"

# 微信小程序主包 < 2MB 限制检查
SIZE_KB=$(du -sk "$OUT_DIR" | awk '{print $1}')
if [ "$SIZE_KB" -gt 2048 ]; then
  echo "⚠️  主包超过 2MB ($SIZE_KB KB), 建议拆分包"
fi

echo "=== 4. 输出位置 ==="
echo "  $OUT_DIR"
echo "  下一步: 用微信开发者工具导入此目录"

# CI 模式: 用 miniprogram-ci 上传体验版
if [ -n "${WECHAT_CI_PRIVATE_KEY:-}" ]; then
  echo "=== 5. CI 上传体验版 ==="
  npx miniprogram-ci upload \
    --pp "$OUT_DIR" \
    --pkp "$WECHAT_CI_PRIVATE_KEY" \
    --appid "$WECHAT_APPID" \
    --uv "$(date +%Y.%m.%d)" \
    --uda "CI build $(git rev-parse --short HEAD)" \
    --enable-es6 true \
    --enable-es7 true
fi
