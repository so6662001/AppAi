<script setup lang="ts">
import type { CardAction } from '@/types/briefing';
import { useActions } from '@/composables/useActions';

const props = defineProps<{ cardId: number; actions: CardAction[] }>();
const { run } = useActions();
</script>

<template>
  <view class="actions">
    <button
      v-for="(a, i) in actions" :key="i"
      :class="['act-btn', i === 0 ? 'primary' : 'default']"
      size="mini"
      @tap="run(cardId, a)"
    >{{ a.label }}</button>
  </view>
</template>

<style scoped>
.actions { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 16rpx; }
.act-btn {
  font-size: 24rpx; padding: 8rpx 20rpx; min-width: 0; margin: 0;
  border-radius: 32rpx; line-height: 1.5;
}
.act-btn::after { border: none; }
.act-btn.primary { background: #1989fa; color: #fff; }
.act-btn.default { background: #f5f7fa; color: #1f2937; }
</style>
