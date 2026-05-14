<script setup lang="ts">
import type { BriefingCard } from '@/types/briefing';
import CardWrapper from '../CardWrapper.vue';
import CardActions from '../CardActions.vue';
import ChartBlock from '../ChartBlock.vue';

defineProps<{ card: BriefingCard }>();
const emit = defineEmits<{
  ignore: [];
  feedback: [vote: 'UP' | 'DOWN'];
}>();

function hasChart(p: any): boolean {
  return p && typeof p === 'object' && p.chart_type && Array.isArray(p.rows);
}
</script>

<!-- 兜底: INSIGHT/ABC/ANOMALY/RECOMMEND 使用通用模板 -->
<template>
  <CardWrapper :card-id="card.card_id" :severity="card.severity" :title="card.title"
    @ignore="emit('ignore')" @feedback="(v) => emit('feedback', v)">
    <view class="payload">
      <ChartBlock v-if="hasChart(card.payload)"
                  :chart="card.payload.chart_type"
                  :x="card.payload.x"
                  :series="card.payload.series || []"
                  :rows="card.payload.rows" />
      <text v-else>{{ typeof card.payload === 'string' ? card.payload : JSON.stringify(card.payload) }}</text>
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.payload { color: #1f2937; font-size: 26rpx; line-height: 1.6; }
</style>
