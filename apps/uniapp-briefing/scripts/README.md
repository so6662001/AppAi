# uniapp 构建脚本

## 微信小程序

### 本地构建 + 用开发者工具打开

```bash
cd apps/uniapp-briefing
bash scripts/build-mp-weixin.sh
# 产物在 dist/build/mp-weixin/
# 用 微信开发者工具 → 导入项目 → 选这个目录
```

### CI 自动上传体验版

需要这些 GitHub Secrets：

| Secret | 说明 |
|--------|------|
| `WECHAT_APPID` | 小程序 AppID |
| `WECHAT_CI_PRIVATE_KEY` | miniprogram-ci 私钥文件内容（在小程序后台-开发设置申请） |

GitHub Actions 中：
```yaml
- name: Build & upload to WeChat
  working-directory: apps/uniapp-briefing
  env:
    WECHAT_APPID: ${{ secrets.WECHAT_APPID }}
    WECHAT_CI_PRIVATE_KEY: ${{ secrets.WECHAT_CI_PRIVATE_KEY }}
  run: bash scripts/build-mp-weixin.sh
```

### 真机预览

```bash
npm run dev:mp-weixin    # 监听变更
# 微信开发者工具 → 预览 → 手机扫码
```

### 上线流程

1. 提交代码到 main
2. CI 自动跑 `bash scripts/build-mp-weixin.sh` 上传**体验版**
3. 团队内测 (扫描体验版二维码)
4. 微信小程序后台 → 版本管理 → **提审**
5. 微信审核（1-3 天）
6. 审核通过 → **发布**

### 主包大小控制

微信主包 < 2MB 是硬限制。当前我们的代码包含 ECharts 已经接近上限，建议：
- 分包：把 `pages/scheduled-report/*` 放分包
- 按需引入 ECharts 组件
- 图片走 CDN
