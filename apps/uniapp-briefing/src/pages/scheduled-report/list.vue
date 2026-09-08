<script setup lang="ts">
import { onLoad, onShow } from '@dcloudio/uni-app';
import { ref } from 'vue';
import { scheduledReportApi, fakeReports } from '@/services/scheduled-report';
import type { ScheduledReport } from '@/types/scheduled-report';

const list = ref<ScheduledReport[]>([]);
const loading = ref(false);

async function fetchData() {
  loading.value = true;
  try {
    const r = await scheduledReportApi.list();
    list.value = r.items || [];
  } catch {
    list.value = fakeReports();
  } finally {
    loading.value = false;
  }
}

onLoad(fetchData);
onShow(fetchData);

function statusColor(s: string) {
  return s === 'ACTIVE' ? '#67c23a' : s === 'PAUSED' ? '#e6a23c' : '#909399';
}

function scheduleText(r: ScheduledReport) {
  if (r.schedule_type === 'daily') return '每天';
  if (r.schedule_type === 'weekly') return '每周';
  if (r.schedule_type === 'monthly') return '每月';
  if (r.schedule_type === 'once') return '仅一次';
  return r.cron_expr || 'cron';
}

async function togglePause(r: ScheduledReport) {
  try {
    if (r.status === 'ACTIVE') {
      await scheduledReportApi.pause(r.report_id);
      r.status = 'PAUSED';
    } else {
      await scheduledReportApi.resume(r.report_id);
      r.status = 'ACTIVE';
    }
    uni.showToast({ title: r.status === 'ACTIVE' ? '已启动' : '已暂停', icon: 'success' });
  } catch {
    uni.showToast({ title: '操作失败', icon: 'error' });
  }
}

async function runNow(r: ScheduledReport) {
  uni.showLoading({ title: '触发中…' });
  try {
    const res = await scheduledReportApi.runNow(r.report_id);
    uni.hideLoading();
    uni.showToast({ title: `已提交 run #${res.run_id}`, icon: 'success' });
  } catch {
    uni.hideLoading();
    uni.showToast({ title: '触发失败', icon: 'error' });
  }
}

function viewRuns(r: ScheduledReport) {
  uni.navigateTo({ url: `/pages/scheduled-report/runs?id=${r.report_id}&name=${encodeURIComponent(r.name)}` });
}

async function remove(r: ScheduledReport, i: number) {
  const ok = await new Promise<boolean>((resolve) => {
    uni.showModal({ title: '删除', content: `确认删除「${r.name}」?`, success: (x) => resolve(x.confirm) });
  });
  if (!ok) return;
  try {
    await scheduledReportApi.remove(r.report_id);
    list.value.splice(i, 1);
    uni.showToast({ title: '已删除', icon: 'success' });
  } catch {
    uni.showToast({ title: '失败', icon: 'error' });
  }
}

function goTemplates() {
  uni.navigateTo({ url: '/pages/scheduled-report/templates' });
}
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">我的定时报表 ({{ list.length }})</text>
      <view class="tpl-btn" @tap="goTemplates">+ 从模板订阅</view>
    </view>

    <view v-if="loading" class="loading">加载中…</view>
    <view v-else-if="!list.length" class="empty">
      <text>还没有定时报表</text>
      <view class="tpl-btn" @tap="goTemplates">浏览模板</view>
    </view>

    <view v-for="(r, i) in list" :key="r.report_id" class="card">
      <view class="row1">
        <text class="name">{{ r.name }}</text>
        <view class="status" :style="{ color: statusColor(r.status) }">● {{ r.status }}</view>
      </view>
      <view class="desc">{{ r.description || '—' }}</view>
      <view class="row2">
        <text class="meta">📅 {{ scheduleText(r) }} {{ r.cron_expr || '' }}</text>
        <text class="meta">📣 {{ (r.channels || []).join(' / ') }}</text>
      </view>
      <view class="row3">
        <text class="meta">下次: {{ r.next_run_at || '—' }}</text>
        <text class="meta">上次: {{ r.last_run_at || '—' }}</text>
      </view>
      <view class="actions">
        <button size="mini" class="btn" @tap="runNow(r)">立即执行</button>
        <button size="mini" class="btn" @tap="togglePause(r)">{{ r.status === 'ACTIVE' ? '暂停' : '启动' }}</button>
        <button size="mini" class="btn" @tap="viewRuns(r)">历史</button>
        <button size="mini" class="btn danger" @tap="remove(r, i)">删除</button>
      </view>
    </view>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding: 16rpx; }
.header { display: flex; justify-content: space-between; align-items: center; padding: 0 8rpx 16rpx; }
.header .title { font-size: 30rpx; font-weight: 700; color: #1f2937; }
.tpl-btn { background: #1989fa; color: #fff; font-size: 24rpx; padding: 8rpx 20rpx; border-radius: 24rpx; }
.loading, .empty { text-align: center; padding: 80rpx 0; color: #909399; font-size: 26rpx; }
.empty .tpl-btn { margin-top: 24rpx; display: inline-block; }
.card { background: #fff; border-radius: 16rpx; padding: 20rpx 24rpx; margin-bottom: 16rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.04); }
.row1 { display: flex; justify-content: space-between; align-items: center; }
.name { font-size: 28rpx; font-weight: 600; color: #1f2937; }
.status { font-size: 22rpx; }
.desc { color: #909399; font-size: 22rpx; margin-top: 4rpx; }
.row2, .row3 { display: flex; gap: 16rpx; margin-top: 8rpx; }
.meta { color: #6b7280; font-size: 22rpx; }
.actions { display: flex; gap: 8rpx; margin-top: 12rpx; flex-wrap: wrap; }
.btn { font-size: 22rpx; padding: 4rpx 12rpx; min-width: 0; margin: 0; background: #f5f7fa; color: #1f2937; border-radius: 6rpx; }
.btn::after { border: none; }
.btn.danger { background: #fef0f0; color: #f56c6c; }
</style>
