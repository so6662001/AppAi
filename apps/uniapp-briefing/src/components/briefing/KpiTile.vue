<script setup lang="ts">
import { computed } from 'vue';
import type { KpiSpec } from '@/types/briefing';

const props = defineProps<{ kpi: KpiSpec }>();

function fmt(v: number, format: KpiSpec['format']): string {
  if (format === 'amount') {
    if (v >= 1e8) return (v / 1e8).toFixed(2) + ' 亿';
    if (v >= 1e4) return (v / 1e4).toFixed(1) + ' 万';
    return v.toLocaleString();
  }
  if (format === 'ton') {
    if (v >= 1e4) return (v / 1e4).toFixed(2) + ' 万';
    return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
  if (format === 'percent') return (v * 100).toFixed(1) + '%';
  if (format === 'price') return v.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (format === 'days') return v.toFixed(1);
  return String(v);
}

const valueText = computed(() => fmt(props.kpi.value, props.kpi.format));

const trendCls = computed(() => {
  const d = props.kpi.trend?.dir;
  return d === 'up' ? 'up' : d === 'down' ? 'down' : 'flat';
});

const trendText = computed(() => {
  const t = props.kpi.trend;
  if (!t) return '';
  const arrow = t.dir === 'up' ? '▲' : t.dir === 'down' ? '▼' : '—';
  const num = t.delta_pct !== undefined
    ? (t.delta_pct >= 0 ? '+' : '') + (t.delta_pct * 100).toFixed(1) + '%'
    : t.delta_abs !== undefined ? (t.delta_abs >= 0 ? '+' : '') + t.delta_abs : '';
  return `${arrow} ${num}${t.baseline ? ' · ' + t.baseline : ''}`;
});
</script>

<template>
  <view class="kpi-tile">
    <view class="kpi-label">{{ kpi.label }}</view>
    <view class="kpi-value">
      <text class="num">{{ valueText }}</text>
      <text class="unit">{{ kpi.unit }}</text>
    </view>
    <view v-if="kpi.trend" :class="['kpi-trend', trendCls]">{{ trendText }}</view>
  </view>
</template>

<style scoped>
.kpi-tile { display: flex; flex-direction: column; gap: 4rpx; padding: 12rpx; }
.kpi-label { font-size: 22rpx; color: #909399; }
.kpi-value .num { font-size: 40rpx; font-weight: 700; color: #1f2937; }
.kpi-value .unit { font-size: 22rpx; color: #909399; margin-left: 6rpx; }
.kpi-trend { font-size: 22rpx; }
.kpi-trend.up { color: #67c23a; }
.kpi-trend.down { color: #f56c6c; }
.kpi-trend.flat { color: #909399; }
</style>
