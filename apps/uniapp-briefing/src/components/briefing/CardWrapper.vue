<script setup lang="ts">
import { computed } from 'vue';
import type { Severity } from '@/types/briefing';

const props = defineProps<{
  cardId: number;
  severity: Severity;
  title: string;
}>();

const emit = defineEmits<{
  ignore: [];
  feedback: [vote: 'UP' | 'DOWN'];
}>();

const barColor = computed(() => {
  switch (props.severity) {
    case 'CRITICAL': return '#d9001b';
    case 'HIGH':     return '#f56c6c';
    case 'MEDIUM':   return '#e6a23c';
    default:         return '#67c23a';
  }
});

const icon = computed(() => {
  switch (props.severity) {
    case 'CRITICAL': return '🚨';
    case 'HIGH':     return '⚠️';
    case 'MEDIUM':   return '💡';
    default:         return '✅';
  }
});

function showMenu() {
  uni.showActionSheet({
    itemList: ['👍 有用', '👎 没用', '不再显示此类'],
    success: (res) => {
      if (res.tapIndex === 0) emit('feedback', 'UP');
      else if (res.tapIndex === 1) emit('feedback', 'DOWN');
      else if (res.tapIndex === 2) emit('ignore');
    },
  });
}
</script>

<template>
  <view class="card-wrap">
    <view class="bar" :style="{ background: barColor }"></view>
    <view class="card-body">
      <view class="card-header">
        <text class="icon">{{ icon }}</text>
        <text class="title">{{ title }}</text>
        <text class="more" @tap="showMenu">⋯</text>
      </view>
      <slot />
    </view>
  </view>
</template>

<style scoped>
.card-wrap { display: flex; background: #fff; border-radius: 16rpx; box-shadow: 0 2rpx 12rpx rgba(0,0,0,0.04); margin: 12rpx 16rpx; overflow: hidden; }
.bar { width: 8rpx; flex-shrink: 0; }
.card-body { flex: 1; padding: 20rpx 24rpx; }
.card-header { display: flex; align-items: center; margin-bottom: 12rpx; }
.card-header .icon { font-size: 32rpx; margin-right: 8rpx; }
.card-header .title { flex: 1; font-size: 30rpx; font-weight: 600; color: #1f2937; }
.card-header .more { color: #909399; padding: 0 8rpx; font-size: 36rpx; }
</style>
