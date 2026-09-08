<script setup lang="ts">
import type { BriefingCard } from '@/types/briefing';
import SummaryCard from './cards/SummaryCard.vue';
import RiskCard from './cards/RiskCard.vue';
import AdviceCard from './cards/AdviceCard.vue';
import CapitalCard from './cards/CapitalCard.vue';
import ForecastCard from './cards/ForecastCard.vue';
import BalanceCard from './cards/BalanceCard.vue';
import GenericCard from './cards/GenericCard.vue';

defineProps<{ cards: BriefingCard[] }>();
const emit = defineEmits<{
  ignore: [cardId: number];
  feedback: [cardId: number, vote: 'UP' | 'DOWN'];
}>();

const componentMap: Record<string, any> = {
  SUMMARY: SummaryCard,
  RISK: RiskCard,
  ADVICE: AdviceCard,
  CAPITAL: CapitalCard,
  FORECAST: ForecastCard,
  BALANCE: BalanceCard,
};

function getComp(type: string) {
  return componentMap[type] || GenericCard;
}
</script>

<template>
  <view class="feed">
    <component
      v-for="card in cards"
      :key="card.card_id"
      :is="getComp(card.type)"
      :card="card"
      @ignore="emit('ignore', card.card_id)"
      @feedback="(v: 'UP' | 'DOWN') => emit('feedback', card.card_id, v)"
    />
  </view>
</template>

<style scoped>
.feed { padding: 8rpx 0 32rpx; }
</style>
