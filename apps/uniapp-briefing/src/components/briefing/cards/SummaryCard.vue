<script setup lang="ts">
import type { BriefingCard } from '@/types/briefing';
import KpiTile from '../KpiTile.vue';
import CardWrapper from '../CardWrapper.vue';
import CardActions from '../CardActions.vue';

const props = defineProps<{ card: BriefingCard }>();
const emit = defineEmits<{
  ignore: [];
  feedback: [vote: 'UP' | 'DOWN'];
}>();
</script>

<template>
  <CardWrapper :card-id="card.card_id" :severity="card.severity" :title="card.payload.greeting || card.title"
    @ignore="emit('ignore')" @feedback="(v) => emit('feedback', v)">
    <text class="sub">{{ card.payload.date_label }}</text>
    <view class="kpi-grid">
      <KpiTile v-for="(k, i) in card.payload.kpis" :key="i" :kpi="k" />
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.sub { color: #909399; font-size: 22rpx; }
.kpi-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8rpx; margin-top: 8rpx; }
</style>
