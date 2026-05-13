<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app';
import { ref } from 'vue';
import { scheduledReportApi } from '@/services/scheduled-report';
import type { ReportRun } from '@/types/scheduled-report';

const reportId = ref(0);
const name = ref('');
const list = ref<ReportRun[]>([]);

onLoad(async (q) => {
  reportId.value = Number(q?.id);
  name.value = q?.name ? decodeURIComponent(q.name) : '';
  try {
    list.value = await scheduledReportApi.runs(reportId.value, 30);
  } catch {
    list.value = [
      { run_id: 1003, report_id: reportId.value, scheduled_at: '2026-05-13 08:00:00',
        started_at: '2026-05-13 08:00:01', finished_at: '2026-05-13 08:00:04',
        duration_ms: 3120, status: 'SUCCESS', rows_returned: 5,
        result_summary: '昨日销售 1,820 万 / 库存 1.84 亿',
        biz_tokens_charged: 1800,
        push_results: [{ channel: 'INAPP', status: 'SENT', latency_ms: 12 }, { channel: 'WECOM', status: 'SENT', latency_ms: 230 }] },
      { run_id: 1002, report_id: reportId.value, scheduled_at: '2026-05-12 08:00:00',
        started_at: '2026-05-12 08:00:01', finished_at: '2026-05-12 08:00:03',
        duration_ms: 2980, status: 'SUCCESS', rows_returned: 5,
        result_summary: '昨日销售 1,620 万 / 库存 1.82 亿', biz_tokens_charged: 1740 },
      { run_id: 1001, report_id: reportId.value, scheduled_at: '2026-05-11 08:00:00',
        status: 'FAILED', error_code: 'E_COST_EXCEEDED', error_msg: '扫描行数超限',
        duration_ms: 0, biz_tokens_charged: 0 },
    ] as any;
  }
});

function statusColor(s: string) {
  return s === 'SUCCESS' ? '#67c23a' : s === 'FAILED' ? '#f56c6c' : s === 'RUNNING' ? '#1989fa' : '#909399';
}

async function resend(run: ReportRun) {
  uni.showLoading({ title: '推送中…' });
  try {
    await scheduledReportApi.resendRun(run.run_id, {});
    uni.hideLoading();
    uni.showToast({ title: '已重新推送', icon: 'success' });
  } catch {
    uni.hideLoading();
    uni.showToast({ title: '失败', icon: 'error' });
  }
}
</script>

<template>
  <view class="page">
    <view class="hd">{{ name }} 执行历史</view>
    <view v-for="r in list" :key="r.run_id" class="card">
      <view class="row1">
        <text class="time">{{ r.scheduled_at }}</text>
        <text class="status" :style="{ color: statusColor(r.status) }">{{ r.status }}</text>
      </view>
      <view v-if="r.result_summary" class="summary">{{ r.result_summary }}</view>
      <view v-if="r.error_msg" class="err">⚠️ {{ r.error_code }}: {{ r.error_msg }}</view>
      <view class="row2">
        <text class="meta">耗时 {{ r.duration_ms || 0 }}ms</text>
        <text class="meta">行数 {{ r.rows_returned || 0 }}</text>
        <text class="meta">消耗 {{ r.biz_tokens_charged || 0 }} tk</text>
      </view>
      <view v-if="r.push_results?.length" class="row2">
        <text v-for="(p, i) in r.push_results" :key="i" class="meta">
          {{ p.channel }} {{ p.status }} ({{ p.latency_ms }}ms)
        </text>
      </view>
      <view v-if="r.status === 'SUCCESS'" class="actions">
        <button size="mini" class="btn" @tap="resend(r)">重发</button>
      </view>
    </view>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding: 16rpx; }
.hd { padding: 12rpx 8rpx 16rpx; font-size: 26rpx; color: #6b7280; }
.card { background: #fff; border-radius: 16rpx; padding: 16rpx 24rpx; margin-bottom: 12rpx; }
.row1 { display: flex; justify-content: space-between; align-items: center; }
.time { font-size: 24rpx; color: #1f2937; }
.status { font-size: 22rpx; font-weight: 600; }
.summary { font-size: 26rpx; color: #1f2937; margin-top: 4rpx; }
.err { font-size: 24rpx; color: #f56c6c; margin-top: 4rpx; }
.row2 { display: flex; gap: 16rpx; margin-top: 6rpx; flex-wrap: wrap; }
.meta { color: #909399; font-size: 22rpx; }
.actions { margin-top: 8rpx; display: flex; gap: 8rpx; }
.btn { font-size: 22rpx; padding: 4rpx 12rpx; min-width: 0; margin: 0; background: #f5f7fa; color: #1f2937; border-radius: 6rpx; }
.btn::after { border: none; }
</style>
