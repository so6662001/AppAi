# 编译 / 部署 / 试用 全流程指南

本文档让你从零开始把这个钢铁 AI 经营分析平台跑起来。共三种场景：

| 场景 | 适合谁 | 时长 | 说明 |
|------|--------|------|------|
| **A. 一键开发体验** | 想快速看效果 | 10~15 分钟 | Docker Compose 起依赖 + 跑 MVP, 不接业务库 |
| **B. 单机部署** | 试点客户 / POC | 1~2 小时 | 部署到单台 Linux, 接通业务库 |
| **C. 生产部署** | 正式上线 | 1~2 天 | K8s, 高可用, 监控 |

> ⚠️ 本仓库当前阶段只包含 **DSL 编译器** + **Lua 计费脚本** + **2 个前端 MVP** 等可运行模块；Java 后端、AI 编排、风控引擎尚未实现（已有完整设计可继续推进）。所以场景 A 仅能演示 UI + 编译器 + Lua 这部分。

---

## 0. 环境前置（必装）

| 组件 | 最低版本 | 用途 | 安装命令(Ubuntu) |
|------|----------|------|-------------------|
| Git | 2.x | 拉代码 | `sudo apt install git` |
| Docker | 24+ | 容器编排 | [官网](https://docs.docker.com/engine/install/) |
| Docker Compose | 2.x | 一键起依赖 | 随 Docker 安装 |
| Node.js | 18 LTS | 前端构建 | `nvm install 18` |
| Python | 3.10+ | DSL 编译器 | 系统自带或 pyenv |
| Java | 17 LTS | Spring Boot 后端 (后续) | `sudo apt install openjdk-17-jdk` |
| pnpm 或 npm | 8+ | 包管理 | `npm i -g pnpm` |
| HBuilderX | 最新 | uniapp 可视化（可选） | [DCloud 下载](https://www.dcloud.io/hbuilderx.html) |
| 微信开发者工具 | 最新 | 小程序调试 | [微信开放平台下载](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) |

检查：

```bash
bash scripts/check-env.sh
```

---

## A. 一键开发体验（最快）

### A.1 克隆代码

```bash
git clone https://github.com/so6662001/AppAi.git
cd AppAi
git checkout cursor/ai-analytics-design-7bf9
```

### A.2 一键起依赖（Docker Compose）

```bash
bash scripts/dev-up.sh
```

这会启动：

| 服务 | 端口 | 用途 |
|------|------|------|
| StarRocks-FE | 9030 (MySQL 协议) / 8030 (HTTP) | OLAP |
| MySQL 8 | 3306 | 治理/计费/会话/早报 |
| Redis 7 | 6379 | 钱包/缓存/预扣 |
| DSL Compiler | 8000 | Python FastAPI |
| Registry Web | 5173 | Vue 注册中心 |
| Briefing H5 | 5174 | uniapp 早报 H5 |

打开浏览器：
- 指标注册中心：http://localhost:5173
- AI 早报 H5：http://localhost:5174
- DSL 编译器 API 文档：http://localhost:8000/docs

> 后端未起时，两个前端会自动 fallback 到演示数据，可以走查所有 UI。

### A.3 验证 DSL 编译器

```bash
curl -X POST http://localhost:8000/v1/dsl/compile \
  -H "Content-Type: application/json" -d '{
    "dsl": {
      "metrics": ["sales_amount", "ton_gross_profit"],
      "dimensions": ["org.region"],
      "time": {"preset": "last_week", "grain": "day"},
      "compare": {"mode": "wow"}
    },
    "context": {"tenant_id": 1, "user_id": 10, "business_line": "TRADE"}
  }'
```

应返回包含生成的 SQL、参数化、表使用情况、估算行数、业务 token 预估的 JSON。

### A.4 验证 Lua 计费脚本（用 fakeredis）

```bash
cd services/billing-lua
pip install --break-system-packages pytest 'fakeredis[lua]' redis
pytest -v
```

应看到 `12 passed`。

### A.5 关闭

```bash
bash scripts/dev-down.sh
```

---

## B. 单机部署（POC / 试点客户）

适用于：1 台 8 核 32G Linux 服务器，给客户做演示或前期试运行。

### B.1 拓扑

```
┌────────────────────────────────────────────────┐
│  Linux 服务器 (8C/32G/500G SSD)                 │
│                                                 │
│  Nginx (80/443) ──► Registry Web (5173)         │
│                  ──► AI 助手 H5 (uniapp dist)   │
│                  ──► Java 后端 (8080)            │
│                       │                          │
│                       ├──► MySQL (3306)         │
│                       ├──► Redis (6379)         │
│                       ├──► DSL Compiler (8000)  │
│                       └──► StarRocks-FE (9030)  │
│                              └──► StarRocks-BE  │
└────────────────────────────────────────────────┘
                   │
                   ▼  (LAN/VPN)
        ┌──────────────────────┐
        │  客户 SQL Server 2008│
        └──────────────────────┘
                   ↑
                   │  SeaTunnel 跑在客户机房或本机
```

### B.2 部署步骤

**1) 服务器准备**

```bash
# 创建工作目录
sudo mkdir -p /opt/steel-ai && cd /opt/steel-ai
sudo chown $USER:$USER /opt/steel-ai

# 拉代码
git clone https://github.com/so6662001/AppAi.git .
git checkout cursor/ai-analytics-design-7bf9
```

**2) 起基础设施**

```bash
# StarRocks(单机模式)、MySQL、Redis
docker compose -f docker-compose.prod.yml up -d starrocks mysql redis
```

等 1 分钟，让 StarRocks BE 注册到 FE：

```bash
docker exec -it steel-starrocks mysql -h 127.0.0.1 -P 9030 -uroot \
  -e "ALTER SYSTEM ADD BACKEND '127.0.0.1:9050';"
```

**3) 建表**

```bash
# StarRocks 数仓
for f in ddl/00_database.sql ddl/01_dimensions.sql ddl/02_sales.sql \
         ddl/03_inventory.sql ddl/04_production_quality.sql \
         ddl/05_procurement.sql ddl/06_capital_risk_forecast_abc.sql \
         ddl/10_materialized_views.sql; do
  docker exec -i steel-starrocks mysql -h127.0.0.1 -P9030 -uroot < "$f"
done

# MySQL 业务库
for f in ddl/07_governance.sql ddl/08_billing.sql ddl/09_chat_session.sql ddl/11_briefing.sql; do
  docker exec -i steel-mysql mysql -uroot -p$MYSQL_ROOT_PASSWORD < "$f"
done
```

**4) 起服务**

```bash
docker compose -f docker-compose.prod.yml up -d dsl-compiler registry-web briefing-h5
```

**5) Nginx 反向代理**

```nginx
# /etc/nginx/sites-available/steel-ai.conf
server {
  listen 80;
  server_name steel-ai.example.com;

  location /registry/  { proxy_pass http://127.0.0.1:5173/; }
  location /briefing/  { proxy_pass http://127.0.0.1:5174/; }
  location /api/       { proxy_pass http://127.0.0.1:8080/; }
  location /dsl/       { proxy_pass http://127.0.0.1:8000/; }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/steel-ai.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**6) 配 SQL Server 同步**

参考 `data-pipelines/seatunnel/README.md`，安装 SeaTunnel 并配置环境变量，调度器（推荐 DolphinScheduler）按 5/10/15 分钟跑各任务。

**7) HTTPS 证书**

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d steel-ai.example.com
```

### B.3 验证

- 浏览器访问 `https://steel-ai.example.com/registry/` 看到指标列表
- 浏览器访问 `https://steel-ai.example.com/briefing/` 看到早报演示
- 客户业务库的销售订单同步到 `dws_sales_daily`

---

## C. 生产部署（K8s）

仓库目前未提供完整 K8s manifest（设计中），关键要点：

| 项 | 推荐 |
|----|------|
| K8s 发行版 | KubeKey / Rancher RKE2 |
| StarRocks | 用 [starrocks-operator](https://github.com/StarRocks/starrocks-kubernetes-operator)，3 FE + 3 BE 起 |
| MySQL | 主从 + ProxySQL，或 PolarDB / RDS |
| Redis | Redis Cluster 3 主 3 从，或云上托管 |
| 镜像 | 内网 Harbor，CI 自动构建 |
| 监控 | Prometheus + Grafana + AlertManager |
| 日志 | Loki / ELK |
| 链路 | OpenTelemetry → Jaeger |
| Ingress | Nginx Ingress + cert-manager (Let's Encrypt) |
| 备份 | StarRocks 每日全量到 OSS，MySQL binlog 每小时 |

每个服务一个 Deployment + Service + HPA，建议先用单机版打磨 3 个月再上 K8s。

---

## D. uniapp 端测试与试用（重点）

uniapp 一套代码 5 端齐发：H5 / 微信小程序 / App / 钉钉小程序 / 支付宝小程序。下面按场景说。

### D.1 H5 浏览器（最简单，零门槛）

**用 npm 启动**

```bash
cd apps/uniapp-briefing
npm install
npm run dev:h5
```

打开 http://localhost:5174 即可看到早报演示数据。

> 后端未起时自动 fallback；要连真实接口，改 `src/services/briefing.ts` 顶部的 `BASE` 或加 `.env.development`：
>
> ```bash
> echo 'VITE_API_BASE=http://localhost:8080/v1' > apps/uniapp-briefing/.env.development
> ```

**测试要点**
- ✅ 卡片下拉刷新
- ✅ 长按卡片弹反馈菜单
- ✅ 点"追问 AI"会带 dsl 跳路由（暂时跳到 `/pages/ai/chat`，可换成你现有路径）
- ✅ 点"一键暂停"弹二次确认
- ✅ 各严重度色条（绿/黄/红/暗红）

### D.2 微信小程序（推荐用于真实手机试用）

**步骤**

1. **下载并登录**[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. **构建小程序代码**：

   ```bash
   cd apps/uniapp-briefing
   npm install
   npm run dev:mp-weixin
   # 产物在 dist/dev/mp-weixin/
   ```

3. **导入工具**：
   - 点"导入项目" → 目录选 `apps/uniapp-briefing/dist/dev/mp-weixin/`
   - AppID 临时用"测试号"或填你自己的小程序 AppID
   - 编译，左侧模拟器即可看到早报页面

4. **真机预览**：
   - 工具菜单 "预览" → 用微信扫描出现的二维码
   - 手机上立即看到早报

5. **手机调试**：
   - 工具菜单 "真机调试" → 扫码，手机即出现调试入口，可看到 console / network

> ⚠️ 微信小程序限制：
> - 接口域名必须在小程序后台**白名单**中，并强制 HTTPS（开发期可在工具里勾"不校验合法域名"）
> - 不支持动态 `<component :is>` 直接传渲染对象，本仓库 `BriefingFeed.vue` 用 `componentMap` 已规避

### D.3 HBuilderX（DCloud 官方 IDE，最适合 App 打包）

1. 下载并安装 [HBuilderX](https://www.dcloud.io/hbuilderx.html)
2. 文件 → 打开目录，选 `apps/uniapp-briefing/`
3. 菜单 **运行 → 运行到浏览器 → Chrome** （H5）
4. 菜单 **运行 → 运行到手机或模拟器**（App，需要先连 Android/iOS 设备）
5. 菜单 **运行 → 运行到小程序模拟器 → 微信开发者工具**

### D.4 真机扫码试用（H5，最快让客户体验）

```bash
# 1) 起 H5
cd apps/uniapp-briefing
npm run dev:h5

# 2) 让手机和电脑同一 WiFi 后, 获取你电脑的 IP
hostname -I | awk '{print $1}'   # 假设是 192.168.1.20

# 3) 改 vite 配置允许外部访问
# apps/uniapp-briefing/manifest.json 已 port 5174
# vite 默认监听 localhost, 需要改成:
#   server: { host: '0.0.0.0', port: 5174 }
```

把链接 `http://192.168.1.20:5174` 用微信「扫一扫→生成二维码」给客户扫，手机浏览器即可访问。

> 给客户外部演示，推荐用 [frp / cpolar / ngrok] 暴露公网域名。

### D.5 集成进客户现有 uniapp（推荐）

客户已经有 uniapp App，把 `apps/uniapp-briefing` 作为子包整合：

**方式 1：拷贝组件**

```bash
# 拷贝到现有 uniapp 项目
cp -r apps/uniapp-briefing/src/components/briefing existing-app/src/components/
cp -r apps/uniapp-briefing/src/pages/ai-briefing   existing-app/src/pages/
cp    apps/uniapp-briefing/src/types/briefing.ts   existing-app/src/types/
cp    apps/uniapp-briefing/src/services/briefing.ts existing-app/src/services/
cp    apps/uniapp-briefing/src/stores/briefing.ts  existing-app/src/stores/
cp    apps/uniapp-briefing/src/composables/useActions.ts existing-app/src/composables/
```

在现有的 `pages.json` 追加：

```json
{ "path": "pages/ai-briefing/index", "style": { "navigationBarTitleText": "经营早报", "enablePullDownRefresh": true } }
```

首页加入早报入口：

```vue
<template>
  <view class="home">
    <!-- AI 早报区 -->
    <BriefingHeader :date="today" :user-name="user.name" />
    <BriefingFeed :cards="store.feed?.cards || []"
                  @ignore="store.ignore"
                  @feedback="store.feedback" />
    <!-- 原有业务 -->
    <BusinessWidgets />
  </view>
</template>
```

**方式 2：uniapp 分包 / 插件市场**

把 `apps/uniapp-briefing` 打成 [uni-extension 插件](https://uniapp.dcloud.net.cn/plugin/uni_modules.html)，发布到 DCloud 插件市场或私有 npm，按需引入。

### D.6 调试技巧

| 问题 | 解决 |
|------|------|
| 微信小程序 console 看不到日志 | 工具 → 调试器 → Console 面板 |
| H5 接口被 CORS 拦截 | 后端配 `Access-Control-Allow-Origin`, 或 vite proxy 转发 |
| 卡片宽度在小屏挤压 | `rpx` 已自适应, 可用工具的"自定义编译模式 → 设备 iPhone 6 / iPhone 14 Pro" 多机型预览 |
| 接口 401 | localStorage / uni.getStorage 里没 jwt, 先用 `uni.setStorageSync('jwt', '<token>')` 测试 |
| 微信小程序请求合法域名报错 | 工具设置勾"不校验合法域名" (仅本地), 上线必须在后台配 |
| App 离线缓存早报 | 用 `uni.setStorageSync('briefing:cache:' + date, feed)` 自行加 |

---

## E. 后端持续推进的清单（不影响 D 节体验）

如果客户已经准备好让你下沉做正式后端，按这个顺序：

1. **Spring Boot Gateway + Auth**（沿用现有 Java 栈）
2. **billing-service**：集成 Lua 4 脚本 + 写 MySQL ledger
3. **registry-service**：实现 docs/metric-registry/api.openapi.yaml 25 接口
4. **query-engine**：把 DSL 编译器返回的 SQL 用只读账号在 StarRocks 上执行
5. **chat-orchestrator**：Python LangGraph，串联 NL → 意图 → DSL → SQL → 图表 → 总结
6. **briefing-generator**：每天 05:00 用便宜模型 + 规则引擎生成早报卡片
7. **risk-alert-service**：定时扫描指标 + 命中规则推 advice_inbox

每完成一项，就把 docker-compose / k8s manifest 增量加入。

---

## F. 常见问题

### F.1 StarRocks 起不来

```
docker logs steel-starrocks
```

常见：内存不足（StarRocks BE 默认 32G），开发环境调小：

```yaml
# docker-compose.prod.yml 的 starrocks 服务
environment:
  - JAVA_OPTS=-Xms2g -Xmx2g
```

### F.2 SQL Server 2008 连不上

- 驱动版本：JDBC 必须用 `mssql-jdbc-9.x.jar`（10+ 移除了对 2008 的支持）
- 加 `;encrypt=false;trustServerCertificate=true` 参数
- 启用混合身份认证；服务"SQL Server (MSSQLSERVER)" 与 "SQL Server Browser" 都要起

### F.3 注册中心前端连不上后端

```js
// apps/registry-web/vite.config.ts
server: {
  proxy: { '/api': { target: 'http://localhost:8080', changeOrigin: true } }
}
```

### F.4 uniapp H5 在微信里打开样式错乱

微信内置浏览器有些 CSS 兼容问题：
- 避免 `position: sticky`（小程序不支持）
- `rpx` 在 H5 会按 750 设计稿换算成 `px`，注意根元素 font-size
- Logo / icon 用 svg 或字体图标，别用 SVG sprite

### F.5 想让客户先看一眼"长什么样"

最快方案：

```bash
# 你的电脑上
cd apps/uniapp-briefing
npm run dev:h5

# 用 ngrok 或 frp 暴露公网
ngrok http 5174
# 会得到 https://xxxx.ngrok.io
```

把链接发给客户，对方手机微信打开即可。整个早报演示 + 卡片交互全部能体验。

---

## G. 一句话总结

| 想做什么 | 命令 |
|---------|------|
| 看 UI 长什么样 | `bash scripts/dev-up.sh` → 浏览器 5173/5174 |
| 跑测试 | `cd services/dsl-compiler && pytest` / `cd services/billing-lua && pytest` |
| 让客户用手机扫码体验 | `cd apps/uniapp-briefing && npm run dev:h5`，让前端监听 `0.0.0.0`，手机微信扫码 |
| 打微信小程序包 | `npm run dev:mp-weixin` → 微信开发者工具导入 `dist/dev/mp-weixin/` |
| 打 App | HBuilderX 打开项目 → 运行到 Android / iOS |
| 集成到现有 uniapp | 见 `D.5`，拷贝组件 + pages.json + 首页嵌入 |
| 部署到客户机房 | 走 `B. 单机部署`，~ 2 小时 |
