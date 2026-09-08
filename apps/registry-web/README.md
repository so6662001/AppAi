# 指标注册中心前端 (Vue 3 + Element Plus)

## 启动

```bash
cd apps/registry-web
npm install
npm run dev          # http://localhost:5173
```

后端 API 默认指向 `http://localhost:8080`（在 `vite.config.ts` 的 proxy 里改）；后端未起时所有页面会自动 fallback 到演示数据，方便走查 UI。

## 页面清单

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | Overview | 首页, KPI / Owner Top5 / SLA 健康 / Top 调用 / 最近变更 |
| `/metrics` | MetricList | 178 指标列表, 多维筛选 / 排序 / 分页 |
| `/metrics/:code` | MetricDetail | 口径 / SQL 预览 / 历史 / 质量 / 影响 5 个 Tab |
| `/metrics/new` `/metrics/:code/edit` | MetricEditor | 表单 + 试算沙箱 + 影响预览 + 提交审批 |
| `/requests` | ChangeRequests | 变更申请列表 (我的 / 待我审批) |
| `/requests/:id` | ChangeRequestDetail | Diff + 影响分析 + 审批 |
| `/quality` | QualityBoard | 未解决质量事件 + SLA 热力图 |
| `/lineage` | Lineage | 指标血缘图谱 |
| `/subscriptions` | Subscriptions | 我订阅的指标 |
| `/settings` | Settings | SLA 默认值 / 推送渠道 / Git 同步 |

## API 客户端

`src/api/metrics.ts` 完整封装了 `docs/metric-registry/api.openapi.yaml` 中的 25 个接口；所有页面默认走 `/api/registry/v1` 前缀（已配置 Vite proxy）。

```ts
import { metricsApi, changeApi, qualityApi } from '@/api/metrics';

const data = await metricsApi.list({ domain: 'SALES', page: 1, size: 30 });
const detail = await metricsApi.get('M120');
const sql = await metricsApi.previewSql('M120', { dimensions: ['org.region'], time: { preset: 'last_month' } });
```

## 鉴权

请求拦截器自动从 `localStorage.jwt` 取 token 注入 `Authorization: Bearer`。生产环境对接 SSO 后改这一处即可。
