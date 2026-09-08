# uniapp · AI 经营早报 MVP

可直接打包到 H5 / 微信小程序 / App。后端未起时所有页面自动 fallback 到演示数据。

## 启动

```bash
cd apps/uniapp-briefing
npm install
npm run dev:h5            # http://localhost:5174
npm run dev:mp-weixin     # 用微信开发者工具打开 dist/dev/mp-weixin
```

或直接导入 HBuilderX 运行。

## 工程结构

```
src/
├─ types/briefing.ts            类型定义 (BriefingFeed, CardAction, KpiSpec...)
├─ services/briefing.ts         API + 演示数据
├─ stores/briefing.ts           Pinia 状态机
├─ composables/useActions.ts    卡片按钮统一调度 (chat/action/navigate)
├─ components/briefing/
│   ├─ BriefingHeader.vue
│   ├─ BriefingFeed.vue         卡片流路由
│   ├─ CardWrapper.vue          通用外壳 (严重度色条 + 长按菜单)
│   ├─ CardActions.vue          按钮组
│   ├─ KpiTile.vue              KPI 单元 (4 选 1)
│   └─ cards/
│       ├─ SummaryCard.vue
│       ├─ RiskCard.vue
│       ├─ AdviceCard.vue
│       ├─ CapitalCard.vue
│       ├─ ForecastCard.vue
│       ├─ BalanceCard.vue
│       └─ GenericCard.vue       INSIGHT/ABC/ANOMALY/RECOMMEND 兜底
└─ pages/ai-briefing/
    ├─ index.vue                主页 (下拉刷新)
    ├─ history.vue
    └─ layout-setting.vue
```

## 演示数据

未连接后端时, 自动加载 `services/briefing.ts` 里的 `fakeFeed()`, 包含 6 张卡片:
摘要 / 风险(授信使用率 98.6%) / 建议(加快出货) / 客户资金占用 Top5 / 预测(下周吨毛利) / 余额提醒。

## 集成进现有 App

把这套作为一个 **subpackages** 引入，或者把 `pages/ai-briefing/index` 内嵌到首页顶部：

```vue
<!-- 首页 -->
<template>
  <view class="home">
    <BriefingHeader :date="today" />
    <BriefingFeed :cards="store.feed?.cards || []" @ignore="..." @feedback="..." />
    <view class="more" @tap="...">查看历史</view>
    <BusinessHomeWidgets />
  </view>
</template>
```

## 关键交互

- **下拉刷新**: 重新拉早报
- **长按卡片**: 弹菜单 (👍 有用 / 👎 没用 / 不再显示)
- **追问 AI**: 携带 dsl 跳到聊天页
- **业务操作** (如"暂停发货"): 有 `confirm` 配置的二次确认
- **离线/弱网**: 接口失败自动 fallback 演示数据

## 卡片渲染逻辑

`BriefingFeed.vue` 根据 `card.type` 路由到对应组件; 未定义的类型走 `GenericCard.vue` 兜底, 确保任何后端新增类型不致白屏。

## 待办

- [ ] MiniChart sparkline (SVG path 自绘, 小程序友好)
- [ ] ECharts 折线图 (InsightCard 用)
- [ ] WebSocket 实时插入 CRITICAL 卡片
- [ ] uni-push 通知接入
