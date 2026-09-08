# uniapp 端速查 (3 分钟跑起来)

只看你需要的那一节即可。

## 方式 1: 浏览器（最快, 0 配置）

```bash
cd apps/uniapp-briefing
npm install
npm run dev:h5
```

浏览器打开 http://localhost:5174 → 立刻看到完整早报演示。

---

## 方式 2: 真机扫码（手机微信浏览器）

```bash
# 一键启动 + 显示局域网 IP
bash scripts/uniapp-h5-host.sh
```

终端会打印类似：

```
本机访问:   http://localhost:5174
局域网访问: http://192.168.1.20:5174
```

**手机操作**:
1. 连同一 WiFi
2. 微信"扫一扫"右上角"⋯" → 用文字方式录入 URL 生成二维码, 再扫
3. 也可以让另一台手机直接在 Chrome 输入 URL

**对外演示**（让客户在公网试用）:

```bash
# 安装 ngrok 或 cpolar
ngrok http 5174
# 得到 https://xxxx.ngrok-free.app, 发给客户
```

---

## 方式 3: 微信小程序（推荐用于上线前真机测试）

### 准备
- 下载 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 并登录
- 准备一个**测试号**或正式 AppID（个人微信号扫码登录后台即可）

### 步骤

```bash
cd apps/uniapp-briefing
npm install
npm run dev:mp-weixin
# 产物在: apps/uniapp-briefing/dist/dev/mp-weixin
```

打开**微信开发者工具**:

1. **导入项目** → 项目目录选 `apps/uniapp-briefing/dist/dev/mp-weixin/`
2. AppID 填测试号或自己的
3. 左侧"详情"→"本地设置"→ 勾选：
   - ✅ 不校验合法域名(开发期)
   - ✅ 不校验 HTTPS 证书
4. 顶栏 **编译** → 左侧模拟器看到效果

### 真机预览（手机微信看效果）

工具顶栏 **预览** → 出现二维码 → 手机微信扫 → 立刻看到。

### 真机调试（手机微信 + Devtools）

工具顶栏 **真机调试** → 手机扫 → 出现调试入口 → 工具上能看到 console、network 等。

---

## 方式 4: 安卓 / iOS App

**最简**：用 [HBuilderX](https://www.dcloud.io/hbuilderx.html)

1. 下载 HBuilderX
2. 文件 → 打开目录 → 选 `apps/uniapp-briefing/`
3. 菜单 **运行 → 运行到手机或模拟器 → 运行到 Android App 基座** （或 iOS）
4. 第一次会要求登录 DCloud 账号

> uniapp 的 App 打包要走 DCloud 云打包或本地打包，参考 [官方文档](https://uniapp.dcloud.net.cn/tutorial/app-base.html)。

---

## 方式 5: 集成到客户现有 uniapp（生产推荐）

### 5.1 把组件拷贝过去

```bash
# 假设客户项目在 /path/to/customer-app
EXISTING=/path/to/customer-app/src

cp -r apps/uniapp-briefing/src/components/briefing        $EXISTING/components/
cp -r apps/uniapp-briefing/src/pages/ai-briefing          $EXISTING/pages/
cp    apps/uniapp-briefing/src/types/briefing.ts          $EXISTING/types/
cp    apps/uniapp-briefing/src/services/briefing.ts       $EXISTING/services/
cp    apps/uniapp-briefing/src/stores/briefing.ts         $EXISTING/stores/
cp    apps/uniapp-briefing/src/composables/useActions.ts  $EXISTING/composables/
```

### 5.2 注册页面 (`pages.json`)

```json
{
  "pages": [
    /* 现有页面 */
    {
      "path": "pages/ai-briefing/index",
      "style": {
        "navigationBarTitleText": "经营早报",
        "enablePullDownRefresh": true
      }
    },
    { "path": "pages/ai-briefing/history",        "style": { "navigationBarTitleText": "历史早报" } },
    { "path": "pages/ai-briefing/layout-setting", "style": { "navigationBarTitleText": "早报设置" } }
  ]
}
```

### 5.3 首页嵌入早报区

```vue
<!-- pages/index/index.vue -->
<script setup>
import BriefingHeader from '@/components/briefing/BriefingHeader.vue';
import BriefingFeed   from '@/components/briefing/BriefingFeed.vue';
import { useBriefingStore } from '@/stores/briefing';
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app';

const store = useBriefingStore();
onLoad(() => store.loadToday());
onPullDownRefresh(async () => { await store.refresh(); uni.stopPullDownRefresh(); });
</script>

<template>
  <view class="home">
    <!-- 顶部 AI 经营早报 -->
    <BriefingHeader date="05-13 周三" user-name="张总" />
    <BriefingFeed :cards="store.feed?.cards || []"
                  @ignore="store.ignore"
                  @feedback="store.feedback" />

    <view class="more" @tap="() => uni.navigateTo({url:'/pages/ai-briefing/index'})">
      查看更多 ›
    </view>

    <!-- 你原来的首页内容 -->
    <BusinessWidgets />
  </view>
</template>
```

### 5.4 配后端域名

```bash
# 客户项目根目录新建 .env.production
echo "VITE_API_BASE=https://api.steel-erp.com/v1" > .env.production
```

如果是微信小程序，**记得在小程序后台的"开发管理 → 服务器域名"里添加该域名**，否则线上无法请求。

### 5.5 验证

- 编译后首页顶部就有早报卡片
- 没接通后端时显示演示数据
- 接通后端时实时拉取 `/v1/briefing/today`

---

## 调试技巧

| 现象 | 排查 |
|------|------|
| 微信小程序请求被拦 `urlNotInDomainList` | 工具→设置→勾"不校验合法域名"; 上线前在小程序后台配 |
| 卡片在 iPhone Mini 上太挤 | 已用 `rpx`, 验证根字号; 必要时把 `kpi-grid` 改 `gap` |
| 请求 401 | `uni.setStorageSync('jwt', '<your-jwt>')` 后刷新 |
| H5 跨域报错 | 后端加 `Access-Control-Allow-Origin: *`, 或 vite proxy |
| 长按菜单不弹 | 微信小程序需用 `@longpress` 替换 `tap`; 已用 `more` 按钮兜底 |
| 暗黑模式 | 当前未做; 可在 CardWrapper 加 `@media (prefers-color-scheme: dark)` |
| 离线缓存 | 在 `stores/briefing.ts` 的 `loadToday` 里加 storage fallback |

---

## 一句话

```bash
# 浏览器看效果
cd apps/uniapp-briefing && npm i && npm run dev:h5

# 手机扫码看效果
bash scripts/uniapp-h5-host.sh

# 微信小程序看效果
cd apps/uniapp-briefing && npm i && npm run dev:mp-weixin
# 然后微信开发者工具导入 dist/dev/mp-weixin/
```
