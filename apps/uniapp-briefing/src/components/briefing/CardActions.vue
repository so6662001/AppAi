<script setup lang="ts">
import type { CardAction } from '@/types/briefing';
import { useActions } from '@/composables/useActions';
import { t } from '@/i18n';

const props = defineProps<{ cardId: number; actions: CardAction[] }>();
const { run } = useActions();

function i18nLabel(a: CardAction): string {
  // 已知动作类型尝试映射到 i18n
  if (a.type === 'chat' && a.label === '追问 AI') return t('action.askAi');
  if (a.type === 'navigate' && a.label === '查看详情') return t('action.detail');
  return a.label;
}
</script>

<template>
  <view class="actions">
    <button
      v-for="(a, i) in actions" :key="i"
      :class="['act-btn', i === 0 ? 'primary' : 'default']"
      size="mini"
      @tap="run(cardId, a)"
    >{{ i18nLabel(a) }}</button>
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
