<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app';
import { ref } from 'vue';
import { scheduledReportApi, fakeTemplates } from '@/services/scheduled-report';
import type { ReportTemplate } from '@/types/scheduled-report';

const list = ref<ReportTemplate[]>([]);
const businessLine = ref<string>('TRADE');

async function fetchData() {
  try {
    list.value = await scheduledReportApi.templates({ business_line: businessLine.value });
  } catch {
    list.value = fakeTemplates().filter(t => !businessLine.value || t.business_line === businessLine.value);
  }
}
onLoad(fetchData);

function pickLine(line: string) {
  businessLine.value = line;
  fetchData();
}

async function subscribe(t: ReportTemplate) {
  const ok = await new Promise<boolean>((resolve) => {
    uni.showModal({
      title: '订阅',
      content: `订阅【${t.name}】, 调度: ${t.cron_expr}, 渠道: ${t.channels.join(', ')}`,
      success: (x) => resolve(x.confirm),
    });
  });
  if (!ok) return;
  try {
    await scheduledReportApi.subscribeTemplate(t.template_id);
    uni.showToast({ title: '已订阅', icon: 'success' });
    setTimeout(() => uni.navigateBack(), 600);
  } catch {
    uni.showToast({ title: '失败', icon: 'error' });
  }
}
</script>

<template>
  <view class="page">
    <view class="tabs">
      <view :class="['tab', businessLine === 'TRADE' ? 'on' : '']" @tap="pickLine('TRADE')">钢贸</view>
      <view :class="['tab', businessLine === 'PROCESS' ? 'on' : '']" @tap="pickLine('PROCESS')">加工</view>
      <view :class="['tab', businessLine === 'MILL' ? 'on' : '']" @tap="pickLine('MILL')">钢厂</view>
    </view>

    <view v-for="t in list" :key="t.template_id" class="card" @tap="subscribe(t)">
      <view class="row1">
        <text class="name">{{ t.name }}</text>
        <text class="cat">{{ t.category }}</text>
      </view>
      <view class="desc">{{ t.description }}</view>
      <view class="row2">
        <text class="meta">📅 {{ t.cron_expr }}</text>
        <text class="meta">📣 {{ t.channels.join(' / ') }}</text>
        <text class="meta">🔥 {{ t.popularity || 0 }} 人在用</text>
      </view>
      <view class="cta">点击订阅 ›</view>
    </view>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding: 16rpx; }
.tabs { display: flex; gap: 8rpx; margin-bottom: 16rpx; }
.tab { flex: 1; text-align: center; padding: 16rpx 0; background: #fff; border-radius: 8rpx; font-size: 26rpx; color: #6b7280; }
.tab.on { background: #1989fa; color: #fff; }
.card { background: #fff; border-radius: 16rpx; padding: 20rpx 24rpx; margin-bottom: 16rpx; }
.row1 { display: flex; justify-content: space-between; align-items: center; }
.name { font-size: 28rpx; font-weight: 600; color: #1f2937; }
.cat { font-size: 22rpx; color: #1989fa; background: #ecf5ff; padding: 2rpx 12rpx; border-radius: 4rpx; }
.desc { color: #6b7280; font-size: 24rpx; margin-top: 4rpx; }
.row2 { display: flex; gap: 16rpx; margin-top: 8rpx; flex-wrap: wrap; }
.meta { color: #909399; font-size: 22rpx; }
.cta { color: #1989fa; font-size: 24rpx; text-align: right; margin-top: 8rpx; }
</style>
