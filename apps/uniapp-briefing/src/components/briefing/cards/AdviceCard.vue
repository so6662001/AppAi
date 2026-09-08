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
    <view class="ctx">{{ card.payload.context }}</view>
    <view class="reason">{{ card.payload.reason }}</view>
    <view class="suggest">
      <text class="title">建议:</text>
      <view v-for="(a, i) in card.payload.suggested_actions" :key="i" class="item">
        · <text class="label">{{ a.label }}</text>
        <text v-if="a.detail" class="detail">{{ a.detail }}</text>
      </view>
    </view>
    <CardActions :card-id="card.card_id" :actions="card.actions" />
  </CardWrapper>
</template>

<style scoped>
.ctx { color: #1989fa; font-weight: 600; font-size: 26rpx; margin-bottom: 4rpx; }
.reason { color: #6b7280; font-size: 24rpx; margin-bottom: 8rpx; line-height: 1.6; }
.suggest .title { color: #e6a23c; font-size: 24rpx; font-weight: 600; }
.item { font-size: 26rpx; color: #1f2937; margin-top: 6rpx; }
.item .label { font-weight: 600; }
.item .detail { color: #6b7280; margin-left: 8rpx; }
</style>
