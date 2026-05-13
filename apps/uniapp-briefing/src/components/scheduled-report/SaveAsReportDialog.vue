<script setup lang="ts">
/**
 * 「另存为定时报表」对话框 - 聊天页里用
 *
 * 用法:
 *   <SaveAsReportDialog
 *     :visible="show"
 *     :dsl="lastDsl"
 *     :question="lastQuestion"
 *     @close="show = false"
 *     @saved="(r) => onSaved(r)"
 *   />
 */
import { ref, computed, watch } from 'vue';
import { scheduledReportApi } from '@/services/scheduled-report';
import type { ScheduleType, PushChannel, ScheduledReport } from '@/types/scheduled-report';

const props = defineProps<{
  visible: boolean;
  dsl: Record<string, any>;
  question?: string;
}>();
const emit = defineEmits<{ close: []; saved: [report: ScheduledReport] }>();

const name = ref('');
const scheduleType = ref<ScheduleType>('daily');
const dailyHour = ref(8);
const weekday = ref(1);          // 1=Mon ... 7=Sun
const monthDay = ref(1);
const cronExpr = ref('0 0 8 * * ?');
const channels = ref<PushChannel[]>(['INAPP']);
const submitting = ref(false);

const channelOptions: { v: PushChannel; label: string }[] = [
  { v: 'INAPP', label: 'App 站内信' },
  { v: 'WECOM', label: '企业微信' },
  { v: 'DINGTALK', label: '钉钉' },
  { v: 'EMAIL', label: '邮件' },
  { v: 'UNI_PUSH', label: '系统推送' },
];

watch(() => props.question, (q) => {
  if (q && !name.value) name.value = q.length > 20 ? q.slice(0, 20) + '...' : q;
}, { immediate: true });

const finalCron = computed(() => {
  if (scheduleType.value === 'cron') return cronExpr.value;
  if (scheduleType.value === 'daily') return `0 0 ${dailyHour.value} * * ?`;
  if (scheduleType.value === 'weekly') {
    const dows = ['?', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN'];
    return `0 0 ${dailyHour.value} ? * ${dows[weekday.value]}`;
  }
  if (scheduleType.value === 'monthly') return `0 0 ${dailyHour.value} ${monthDay.value} * ?`;
  return cronExpr.value;
});

const previewText = computed(() => {
  if (scheduleType.value === 'daily') return `每天 ${dailyHour.value}:00`;
  if (scheduleType.value === 'weekly') return `每周${['','一','二','三','四','五','六','日'][weekday.value]} ${dailyHour.value}:00`;
  if (scheduleType.value === 'monthly') return `每月 ${monthDay.value} 号 ${dailyHour.value}:00`;
  return `cron: ${cronExpr.value}`;
});

function toggleChannel(c: PushChannel) {
  const i = channels.value.indexOf(c);
  if (i >= 0) channels.value.splice(i, 1);
  else channels.value.push(c);
}

function close() { emit('close'); }

async function save() {
  if (!name.value.trim()) {
    uni.showToast({ title: '请输入报表名称', icon: 'none' });
    return;
  }
  if (!channels.value.length) {
    uni.showToast({ title: '请至少选择一个推送渠道', icon: 'none' });
    return;
  }
  submitting.value = true;
  try {
    const r = await scheduledReportApi.create({
      name: name.value,
      dsl_json: props.dsl,
      question: props.question,
      schedule_type: scheduleType.value,
      cron_expr: finalCron.value,
      channels: channels.value,
      source: 'chat',
    });
    uni.showToast({ title: '已保存', icon: 'success' });
    emit('saved', r);
    close();
  } catch (e: any) {
    uni.showToast({ title: '保存失败', icon: 'error' });
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <view v-if="visible" class="mask" @tap="close">
    <view class="sheet" @tap.stop>
      <view class="title">保存为定时报表</view>

      <view class="row">
        <text class="label">名称</text>
        <input v-model="name" class="input" placeholder="给报表起个名字" />
      </view>

      <view class="row">
        <text class="label">频率</text>
        <view class="pills">
          <view :class="['pill', scheduleType === 'daily' ? 'on' : '']" @tap="scheduleType = 'daily'">每天</view>
          <view :class="['pill', scheduleType === 'weekly' ? 'on' : '']" @tap="scheduleType = 'weekly'">每周</view>
          <view :class="['pill', scheduleType === 'monthly' ? 'on' : '']" @tap="scheduleType = 'monthly'">每月</view>
          <view :class="['pill', scheduleType === 'cron' ? 'on' : '']" @tap="scheduleType = 'cron'">高级</view>
        </view>
      </view>

      <view v-if="scheduleType !== 'cron'" class="row">
        <text class="label">时间</text>
        <picker mode="selector" :range="['7:00','8:00','9:00','10:00','11:00','12:00','14:00','17:00','18:00','19:00','20:00']"
                @change="(e: any) => dailyHour = [7,8,9,10,11,12,14,17,18,19,20][e.detail.value]">
          <view class="picker">{{ dailyHour }}:00</view>
        </picker>
        <picker v-if="scheduleType === 'weekly'" mode="selector"
                :range="['周一','周二','周三','周四','周五','周六','周日']"
                @change="(e: any) => weekday = e.detail.value + 1">
          <view class="picker" style="margin-left:8rpx;">{{ ['','一','二','三','四','五','六','日'][weekday] }}</view>
        </picker>
        <picker v-if="scheduleType === 'monthly'" mode="selector"
                :range="Array.from({length:28},(_,i)=>String(i+1)+'号')"
                @change="(e: any) => monthDay = e.detail.value + 1">
          <view class="picker" style="margin-left:8rpx;">{{ monthDay }} 号</view>
        </picker>
      </view>

      <view v-else class="row">
        <text class="label">cron</text>
        <input v-model="cronExpr" class="input" placeholder="0 0 8 * * ?" />
      </view>

      <view class="row preview">⏰ {{ previewText }}</view>

      <view class="row">
        <text class="label">推送</text>
        <view class="pills">
          <view v-for="c in channelOptions" :key="c.v"
                :class="['pill', channels.includes(c.v) ? 'on' : '']"
                @tap="toggleChannel(c.v)">{{ c.label }}</view>
        </view>
      </view>

      <view class="actions">
        <button class="btn" @tap="close">取消</button>
        <button class="btn primary" :loading="submitting" @tap="save">保存</button>
      </view>
    </view>
  </view>
</template>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 99; display: flex; align-items: flex-end; }
.sheet { width: 100%; background: #fff; border-radius: 24rpx 24rpx 0 0; padding: 32rpx 24rpx 48rpx; }
.title { font-size: 32rpx; font-weight: 700; color: #1f2937; margin-bottom: 16rpx; }
.row { display: flex; align-items: center; gap: 12rpx; margin-bottom: 16rpx; flex-wrap: wrap; }
.label { color: #6b7280; font-size: 26rpx; width: 80rpx; }
.input { flex: 1; background: #f5f7fa; border-radius: 8rpx; padding: 12rpx 16rpx; font-size: 26rpx; }
.picker { background: #f5f7fa; padding: 8rpx 24rpx; border-radius: 8rpx; font-size: 26rpx; }
.pills { display: flex; flex-wrap: wrap; gap: 8rpx; flex: 1; }
.pill { background: #f5f7fa; color: #6b7280; padding: 8rpx 20rpx; border-radius: 24rpx; font-size: 24rpx; }
.pill.on { background: #1989fa; color: #fff; }
.preview { color: #1989fa; font-size: 26rpx; padding-left: 92rpx; }
.actions { display: flex; gap: 12rpx; margin-top: 24rpx; }
.btn { flex: 1; background: #f5f7fa; color: #1f2937; font-size: 28rpx; border-radius: 8rpx; }
.btn.primary { background: #1989fa; color: #fff; }
.btn::after { border: none; }
</style>
