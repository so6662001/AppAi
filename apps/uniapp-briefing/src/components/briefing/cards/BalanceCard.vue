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
    <view class="balance">
      <text class="num">{{ card.payload.current.toLocaleString() }}</text>
      <text class="sep">/</text>
      <text class="total">{{ card.payload.total.toLocaleString() }}</text>
    </view>
    <view class="usage">本月已用 {{ (card.payload.used_pct * 100).toFixed(1) }}%, {{ card.payload.eta }}</view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.balance { font-size: 32rpx; font-weight: 700; color: #1f2937; }
.balance .total { color: #909399; font-weight: 400; }
.balance .sep { color: #909399; margin: 0 4rpx; }
.usage { color: #f56c6c; font-size: 24rpx; margin-top: 6rpx; }
</style>
