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
    <view class="row" v-for="(m, i) in card.payload.metrics" :key="i">
      <text class="lbl">{{ m.label }}</text>
      <text :class="['val', m.sub === 'HIGH' ? 'danger' : '']">{{ m.value }}</text>
    </view>
    <view v-if="card.payload.risk_score !== undefined" class="row">
      <text class="lbl">风险评分</text>
      <text class="val danger">{{ card.payload.risk_score }}</text>
    </view>
    <view v-if="card.payload.ai_advice?.length" class="advice">
      <text class="advice-title">AI 建议</text>
      <view v-for="(a, i) in card.payload.ai_advice" :key="i" class="advice-item">· {{ a }}</view>
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.row { display: flex; justify-content: space-between; padding: 6rpx 0; font-size: 26rpx; }
.row .lbl { color: #909399; }
.row .val { color: #1f2937; }
.row .val.danger { color: #f56c6c; font-weight: 600; }
.advice { background: #fff8eb; border-radius: 12rpx; padding: 16rpx; margin-top: 12rpx; }
.advice-title { font-size: 24rpx; color: #e6a23c; font-weight: 600; }
.advice-item { font-size: 26rpx; color: #1f2937; margin-top: 6rpx; }
</style>
