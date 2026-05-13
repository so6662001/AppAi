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

<!-- 兜底: INSIGHT/ABC/ANOMALY/RECOMMEND 使用通用模板 -->
<template>
  <CardWrapper :card-id="card.card_id" :severity="card.severity" :title="card.title"
    @ignore="emit('ignore')" @feedback="(v) => emit('feedback', v)">
    <view class="payload">
      <text>{{ typeof card.payload === 'string' ? card.payload : JSON.stringify(card.payload) }}</text>
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.payload { color: #1f2937; font-size: 26rpx; line-height: 1.6; }
</style>
