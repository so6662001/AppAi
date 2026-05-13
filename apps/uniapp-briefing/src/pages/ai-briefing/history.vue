<script setup lang="ts">
import { onLoad } from '@dcloudio/uni-app';
import { ref } from 'vue';
import { briefingApi } from '@/services/briefing';

const list = ref<any[]>([]);

onLoad(async () => {
  try {
    const r = await briefingApi.history('2026-05-01', '2026-05-13', 1, 30);
    list.value = r.items;
  } catch {
    list.value = Array.from({ length: 7 }, (_, i) => ({
      biz_date: `2026-05-${(13 - i).toString().padStart(2, '0')}`,
      card_count: 6 - (i % 3),
    }));
  }
});

function viewDate(date: string) {
  uni.navigateTo({ url: `/pages/ai-briefing/index?date=${date}` });
}
</script>

<template>
  <view class="page">
    <view class="list">
      <view v-for="(it, i) in list" :key="i" class="row" @tap="viewDate(it.biz_date)">
        <text class="date">{{ it.biz_date }}</text>
        <text class="cnt">{{ it.card_count || it.cards?.length || 0 }} 张卡片</text>
        <text class="arrow">›</text>
      </view>
    </view>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding: 16rpx; }
.list { background: #fff; border-radius: 16rpx; }
.row { display: flex; align-items: center; padding: 24rpx 32rpx; border-bottom: 1rpx solid #f0f0f0; }
.row .date { flex: 1; font-size: 28rpx; }
.row .cnt { color: #909399; font-size: 24rpx; margin-right: 16rpx; }
.row .arrow { color: #c0c4cc; }
</style>
