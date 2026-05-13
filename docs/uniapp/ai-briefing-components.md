# AI 早报 uniapp 组件树（详细 Props/Events/接口）

## 1. 工程结构

```
src/
├─ pages/ai-briefing/
│   ├─ index.vue                  早报主页 (App 首页顶部嵌入或独立页)
│   ├─ history.vue                历史早报
│   └─ layout-setting.vue         个性化布局
├─ components/briefing/
│   ├─ BriefingHeader.vue
│   ├─ BriefingFeed.vue           卡片流容器
│   ├─ cards/
│   │   ├─ SummaryCard.vue
│   │   ├─ RiskCard.vue
│   │   ├─ AdviceCard.vue
│   │   ├─ InsightCard.vue
│   │   ├─ AbcCard.vue
│   │   ├─ ForecastCard.vue
│   │   ├─ CapitalCard.vue
│   │   ├─ AnomalyCard.vue
│   │   ├─ RecommendCard.vue
│   │   └─ BalanceCard.vue
│   ├─ CardWrapper.vue            通用卡片外壳 (标题/严重度/折叠)
│   ├─ CardActions.vue            按钮组
│   ├─ TrendBadge.vue             ▲/▼ + 百分比
│   ├─ MiniChart.vue              小型 sparkline
│   └─ KpiTile.vue                单 KPI 单元
├─ composables/
│   ├─ useBriefing.ts             早报数据 + 状态机
│   ├─ usePush.ts                 推送订阅/取消
│   └─ useActions.ts              处理 chat/action/navigate
├─ stores/
│   └─ briefing.ts                pinia
└─ services/api/
    └─ briefing.ts                fetch / put / post
```

## 2. 关键组件接口

### 2.1 `<BriefingFeed>` 容器

```ts
defineProps<{
  feed: BriefingFeed;            // 服务端返回的整个早报
  loading?: boolean;
}>();

defineEmits<{
  refresh:     [];
  cardRead:    [cardId: number];
  cardAct:     [cardId: number, action: CardAction, result: any];
  cardIgnore:  [cardId: number];
  cardFeedback:[cardId: number, vote: 'UP'|'DOWN', reason?: string];
}>();
```

容器职责：
- 把 `feed.cards[]` 按 `card_type` 路由到具体卡片组件
- 监听滚动，自动 mark-read（曝光 > 1s 视为已读）
- 暗黑模式与字号自适应
- 长按卡片唤出菜单（忽略/反馈/分享）

### 2.2 `<CardWrapper>` 通用外壳

```ts
defineProps<{
  cardId:   number;
  severity: 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL';
  title:    string;
  collapsible?: boolean;
  expiresAt?: string;
}>();
```

外观：
- 圆角 12, 阴影 sm, 内边距 16
- 左侧 4px 色条（绿/黄/橙/红）
- 顶部图标 + 标题 + 右侧时间戳/折叠
- 底部 slot 给 `<CardActions>`

### 2.3 `<KpiTile>`（SUMMARY 卡的单元）

```ts
defineProps<{
  metricCode: string;
  label:      string;
  value:      number;
  unit:       string;
  format:     'amount' | 'ton' | 'percent' | 'price' | 'days' | 'count';
  trend?: { dir: 'up'|'down'|'flat'; deltaPct?: number; deltaAbs?: number; baseline?: string };
  sparkline?: number[];      // 7 天小图
}>();

defineEmits<{
  click: [metricCode: string];   // 点击进入指标详情
}>();
```

格式化规则：
- amount: `¥1,820 万 / ¥182 万 / ¥18.2 亿` 自适应
- ton: `4,820 吨 / 4.82 万吨`
- 趋势箭头：up=▲绿 down=▼红 flat=—灰
- 字号: 数字 32sp, label 14sp, 趋势 12sp

### 2.4 `<CardActions>` 通用操作组

```ts
defineProps<{
  cardId:  number;
  actions: CardAction[];        // 见 BriefingCard schema
}>();
```

行为：
- `type=chat` → `uni.navigateTo('/pages/ai/chat?prefillDsl=' + base64(JSON.stringify(action.dsl)))`
- `type=action` → 弹 confirm（若有），调 `useActions().run(action.handler, action.params)`
- `type=navigate` → `uni.navigateTo(action.path)`
- 调用完上报 `POST /briefing/cards/{id}/act`

## 3. 各卡片 Payload Schema

### 3.1 SummaryCard

```ts
interface SummaryPayload {
  greeting: string;       // "早安, 张总"
  date_label: string;     // "05-13 周三"
  kpis: KpiTileSpec[];    // 推荐 4 个
}
```

### 3.2 RiskCard

```ts
interface RiskPayload {
  entity_type: 'CUSTOMER' | 'ORIGIN' | 'HEDGE' | 'AR';
  entity_name: string;
  metrics: Array<{ label: string; value: string; sub?: string }>;
  ai_advice: string[];           // 文本建议
  risk_score?: number;
}
```

### 3.3 AdviceCard

```ts
interface AdvicePayload {
  rule_id: string;                // 命中的规则
  context: string;                // "沙钢 Q355B 热卷"
  reason: string;                 // 为什么建议
  suggested_actions: Array<{ label: string; detail?: string }>;
}
```

### 3.4 InsightCard

```ts
interface InsightPayload {
  metric_label: string;
  current: number;
  baseline: number;
  delta_pct: number;
  chart?: { type: 'line'|'bar'; series: any };
  root_causes: Array<{ label: string; impact: string }>;
}
```

### 3.5 AbcCard / ForecastCard / CapitalCard / AnomalyCard / RecommendCard / BalanceCard

参见 `ai-briefing.md` 各卡片样例。统一约束：
- `payload` 都是 `Record<string, any>`，前端按 type 分发
- 每个卡片最多 4 行核心数据，超过的放二级页

## 4. 状态机（`useBriefing.ts`）

```ts
interface BriefingState {
  feed: BriefingFeed | null;
  loading: boolean;
  error: string | null;
  expandedCardIds: Set<number>;
  readCardIds:     Set<number>;
}

const briefing = useBriefingStore();

// 进入早报页时
onLoad(async () => {
  await briefing.loadToday();
  // 订阅 WebSocket / uni-push, 新卡到达时局部插入
  briefing.subscribeRealtime();
});

// 卡片曝光时
function onCardVisible(cardId: number) {
  if (!briefing.readCardIds.has(cardId)) {
    briefing.markRead(cardId);    // 内部 debounce 500ms 批量上报
  }
}
```

## 5. 实时推送融合

- 严重度=CRITICAL 时，服务端立即 push WebSocket → 前端在卡片流顶部插入一张红色风险卡，同时显示 toast
- 普通早报按计划生成，App 进入时一次性拉取
- 推送链路：`notification-service` → `uni-push` / `wecom` / `dingtalk` 三路并发

## 6. 性能优化

- 卡片懒加载：使用 `uni-list-item` 虚拟滚动，进入视口才挂载内部图表
- `MiniChart` 用 SVG path 自绘，避免 ECharts 重量级初始化
- 图片/图标走 base64 内联或 CDN
- 早报数据按 (tenant, user, date) 缓存到本地 storage，二次进入秒开

## 7. 无障碍

- 严重度色块不依赖颜色单独传达，配 icon + 文字
- 字号支持系统调整，最大 1.5x
- 关键操作按钮 hit 区域 ≥ 44x44

## 8. 埋点

```
briefing.feed.shown            打开早报页
briefing.card.shown            单卡曝光
briefing.card.read             阅读完成
briefing.card.clicked          点击卡片
briefing.card.action_clicked   点击按钮 (action_label, action_type)
briefing.card.acted            执行 action 成功
briefing.card.ignored
briefing.card.feedback         vote, reason
briefing.layout.updated
briefing.push.received         (channel, severity)
briefing.push.clicked
```

写入 `briefing_metrics_daily` 日聚合, 用于 13 节的运营度量。

## 9. 示例（首页嵌入早报区）

```vue
<!-- pages/index.vue -->
<template>
  <view class="home">
    <BalanceBadge />

    <!-- AI 经营早报区 -->
    <BriefingHeader :date="today" :user-name="user.name" />
    <BriefingFeed
      :feed="briefing.feed"
      :loading="briefing.loading"
      @refresh="briefing.refresh"
      @card-act="onCardAct"
      @card-feedback="onCardFeedback"
    />

    <view class="more" @tap="goHistory">查看历史早报 ›</view>

    <!-- 其他原首页内容 -->
    <BusinessHomeWidgets />

    <!-- 浮动 AI 助手按钮 -->
    <AiAssistantFab />
  </view>
</template>
```
