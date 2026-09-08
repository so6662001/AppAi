<script setup lang="ts">
/**
 * AI 聊天页 (简化 MVP, 展示如何接入 SaveAsReportDialog)
 *
 * 真实项目里:
 *   - 接 SSE 流式接口 /v1/chat/messages
 *   - 渲染 KpiTile / TableBlock / ChartBlock / 总结
 *   - 这里只演示对话列表 + 输入 + 「另存为定时报表」入口
 */
import { onLoad } from '@dcloudio/uni-app';
import { ref, computed } from 'vue';
import SaveAsReportDialog from '@/components/scheduled-report/SaveAsReportDialog.vue';
import KpiTile from '@/components/briefing/KpiTile.vue';

interface Msg {
  id: string;
  role: 'user' | 'assistant';
  text?: string;
  blocks?: any[];
  dsl?: Record<string, any>;        // AI 用到的 DSL, 给"另存为定时"用
  question?: string;
}

const messages = ref<Msg[]>([]);
const input = ref('');
const sending = ref(false);

const showSaveDialog = ref(false);
const saveContext = ref<{ dsl: Record<string, any>; question: string }>({
  dsl: {}, question: '',
});

const recommended = [
  '昨天我们的总销售额',
  '上周华东大区A产品达交率',
  '本月吨毛利 Top10 客户',
  '当前库龄 1 年以上的呆滞物料',
];

onLoad((q: any) => {
  // 从早报卡片"追问 AI"过来时, prefillDsl 会带 DSL
  if (q?.prefillDsl) {
    try {
      const dsl = JSON.parse(decodeURIComponent(q.prefillDsl));
      sendMessage('（来自早报追问）', dsl);
    } catch {}
  }
});

async function sendMessage(text: string, prefillDsl?: Record<string, any>) {
  if (!text.trim() && !prefillDsl) return;
  const userMsg: Msg = { id: 'u-' + Date.now(), role: 'user', text };
  messages.value.push(userMsg);
  sending.value = true;

  // === 调真实接口处简化为 mock ===
  await new Promise(r => setTimeout(r, 500));

  // 假设后端编排返回了 DSL + blocks + 总结
  const dsl = prefillDsl || {
    metrics: ['sales_amount', 'ton_gross_profit'],
    dimensions: ['org.region'],
    time: { preset: 'yesterday', grain: 'day' },
  };
  const blocks = [{
    type: 'kpi',
    kpis: [
      { metric: 'sales_amount', label: '销售额', value: 18200000, unit: '元',
        format: 'amount', trend: { dir: 'up', delta_pct: 0.12 } },
      { metric: 'ton_gross_profit', label: '吨毛利', value: 186, unit: '元/吨',
        format: 'price', trend: { dir: 'up', delta_abs: 22 } },
    ],
  }];
  messages.value.push({
    id: 'a-' + Date.now(),
    role: 'assistant',
    text: '已为你查询：昨日华东销售额 1,820 万 (▲ 12%)，吨毛利 186 元/吨。',
    blocks,
    dsl,
    question: text,
  });
  input.value = '';
  sending.value = false;
}

function pickRecommended(q: string) { sendMessage(q); }

function openSaveDialog(msg: Msg) {
  if (!msg.dsl) return;
  saveContext.value = {
    dsl: msg.dsl,
    question: msg.question || '',
  };
  showSaveDialog.value = true;
}

function onReportSaved(report: any) {
  uni.showModal({
    title: '已保存定时报表',
    content: `「${report.name}」将在 ${report.cron_expr || report.schedule_type} 自动执行`,
    showCancel: false,
    success: () => {
      uni.navigateTo({ url: '/pages/scheduled-report/list' });
    },
  });
}
</script>

<template>
  <view class="page">
    <scroll-view scroll-y class="msgs">
      <view v-if="!messages.length" class="welcome">
        <text class="hi">👋 你好, 我是钢铁经营 AI 助手</text>
        <text class="hint">问我任何关于销售、库存、生产、采购的问题</text>
        <view class="recos">
          <view v-for="(q, i) in recommended" :key="i" class="reco" @tap="pickRecommended(q)">{{ q }}</view>
        </view>
      </view>

      <view v-for="m in messages" :key="m.id" :class="['msg', m.role]">
        <view class="bubble" :class="m.role">
          <text v-if="m.text" class="msg-text">{{ m.text }}</text>

          <!-- KPI block -->
          <view v-if="m.blocks?.length" class="blocks">
            <view v-for="(b, bi) in m.blocks" :key="bi">
              <view v-if="b.type === 'kpi'" class="kpi-grid">
                <KpiTile v-for="(k, i) in b.kpis" :key="i" :kpi="k" />
              </view>
            </view>
          </view>

          <!-- 助手消息的快捷操作 -->
          <view v-if="m.role === 'assistant' && m.dsl" class="msg-actions">
            <button class="act-btn primary" size="mini" @tap="openSaveDialog(m)">
              ⏰ 保存为定时报表
            </button>
            <button class="act-btn" size="mini">📤 导出</button>
            <button class="act-btn" size="mini">👍</button>
            <button class="act-btn" size="mini">👎</button>
          </view>
        </view>
      </view>

      <view v-if="sending" class="thinking">AI 思考中…</view>
    </scroll-view>

    <view class="input-bar">
      <input v-model="input" class="input" placeholder="请描述要分析的内容…"
             confirm-type="send" @confirm="sendMessage(input)" />
      <button class="send" :disabled="sending" @tap="sendMessage(input)">发送</button>
    </view>

    <!-- 另存为定时报表对话框 -->
    <SaveAsReportDialog
      :visible="showSaveDialog"
      :dsl="saveContext.dsl"
      :question="saveContext.question"
      @close="showSaveDialog = false"
      @saved="onReportSaved"
    />
  </view>
</template>

<style>
.page { display: flex; flex-direction: column; height: 100vh; background: #f5f7fa; }
.msgs { flex: 1; padding: 16rpx; }
.welcome { padding: 80rpx 32rpx 32rpx; display: flex; flex-direction: column; align-items: center; }
.welcome .hi { font-size: 32rpx; font-weight: 700; color: #1f2937; }
.welcome .hint { font-size: 24rpx; color: #909399; margin: 8rpx 0 24rpx; }
.recos { display: grid; grid-template-columns: 1fr 1fr; gap: 12rpx; width: 100%; }
.reco { background: #fff; padding: 16rpx; border-radius: 12rpx; font-size: 24rpx; text-align: center; color: #1989fa; }
.msg { display: flex; margin-bottom: 16rpx; }
.msg.user { justify-content: flex-end; }
.msg.assistant { justify-content: flex-start; }
.bubble { max-width: 80%; padding: 16rpx 20rpx; border-radius: 16rpx; }
.bubble.user { background: #1989fa; color: #fff; }
.bubble.assistant { background: #fff; color: #1f2937; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.04); }
.msg-text { font-size: 26rpx; line-height: 1.6; }
.blocks { margin-top: 12rpx; }
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8rpx; background: #f5f7fa; border-radius: 8rpx; padding: 8rpx; }
.msg-actions { display: flex; gap: 8rpx; margin-top: 12rpx; flex-wrap: wrap; }
.act-btn { font-size: 22rpx; padding: 4rpx 16rpx; min-width: 0; margin: 0; background: #f5f7fa; color: #1f2937; border-radius: 24rpx; }
.act-btn::after { border: none; }
.act-btn.primary { background: #1989fa; color: #fff; }
.thinking { text-align: center; color: #909399; font-size: 22rpx; padding: 16rpx 0; }
.input-bar { display: flex; gap: 8rpx; padding: 16rpx; background: #fff; border-top: 1rpx solid #eee; }
.input { flex: 1; background: #f5f7fa; border-radius: 32rpx; padding: 16rpx 24rpx; font-size: 26rpx; }
.send { background: #1989fa; color: #fff; font-size: 26rpx; border-radius: 32rpx; min-width: 100rpx; }
.send::after { border: none; }
</style>
