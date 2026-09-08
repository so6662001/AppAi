<script setup lang="ts">
import type { BriefingCard } from '@/types/briefing';
import CardWrapper from '../CardWrapper.vue';
import CardActions from '../CardActions.vue';

defineProps<{ card: BriefingCard }>();
const emit = defineEmits<{
  ignore: [];
  feedback: [vote: 'UP' | 'DOWN'];
}>();
</script>

<template>
  <CardWrapper :card-id="card.card_id" :severity="card.severity" :title="card.title"
    @ignore="emit('ignore')" @feedback="(v) => emit('feedback', v)">
    <view class="metric">{{ card.payload.metric }}</view>
    <view class="forecast">
      <text class="cur">{{ card.payload.current }}</text>
      <text class="arrow">→</text>
      <text :class="['fcst', card.payload.forecast < card.payload.current ? 'down' : 'up']">{{ card.payload.forecast }}</text>
      <text class="unit">元/吨</text>
    </view>
    <view class="ci">90% 置信区间: [{{ card.payload.lower }}, {{ card.payload.upper }}]</view>
    <view class="mape">模型 30 天 MAPE: {{ (card.payload.mape * 100).toFixed(1) }}% ({{ card.payload.confidence === 'high' ? '可信' : '低置信' }})</view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.metric { font-size: 26rpx; color: #6b7280; }
.forecast { font-size: 36rpx; font-weight: 700; margin: 8rpx 0; }
.cur { color: #909399; }
.arrow { margin: 0 12rpx; color: #909399; }
.fcst.up { color: #67c23a; }
.fcst.down { color: #f56c6c; }
.unit { font-size: 22rpx; color: #909399; margin-left: 8rpx; }
.ci, .mape { font-size: 22rpx; color: #909399; margin-top: 4rpx; }
</style>
