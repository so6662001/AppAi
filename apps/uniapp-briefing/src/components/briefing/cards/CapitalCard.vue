<script setup lang="ts">
import type { BriefingCard } from '@/types/briefing';
import CardWrapper from '../CardWrapper.vue';
import CardActions from '../CardActions.vue';

defineProps<{ card: BriefingCard }>();
const emit = defineEmits<{
  ignore: [];
  feedback: [vote: 'UP' | 'DOWN'];
}>();

function fmtAmount(v: number) {
  if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿';
  if (v >= 1e4) return (v / 1e4).toFixed(0) + ' 万';
  return v.toString();
}
function fmtPct(v: number) { return (v * 100).toFixed(1) + '%'; }
function irrClass(v: number) {
  if (v < 0) return 'danger';
  if (v < 0.05) return 'warn';
  return 'ok';
}
</script>

<template>
  <CardWrapper :card-id="card.card_id" :severity="card.severity" :title="card.title"
    @ignore="emit('ignore')" @feedback="(v) => emit('feedback', v)">
    <view class="row" v-for="r in card.payload.rows" :key="r.rank">
      <text class="rank">{{ r.rank }}</text>
      <text class="name">{{ r.name }}</text>
      <text class="cap">占款 ¥{{ fmtAmount(r.capital) }}</text>
      <text :class="['irr', irrClass(r.irr)]">IRR {{ fmtPct(r.irr) }}</text>
      <text class="emoji">{{ r.label }}</text>
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.row { display: flex; align-items: center; font-size: 24rpx; padding: 6rpx 0; }
.rank { width: 30rpx; color: #909399; }
.name { width: 100rpx; color: #1f2937; }
.cap  { flex: 1; color: #6b7280; }
.irr { width: 130rpx; text-align: right; font-weight: 600; }
.irr.ok { color: #67c23a; }
.irr.warn { color: #e6a23c; }
.irr.danger { color: #f56c6c; }
.emoji { width: 40rpx; text-align: right; }
</style>
