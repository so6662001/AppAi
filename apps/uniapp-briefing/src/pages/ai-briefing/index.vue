<script setup lang="ts">
import { onLoad, onPullDownRefresh } from '@dcloudio/uni-app';
import { computed } from 'vue';
import { useBriefingStore } from '@/stores/briefing';
import BriefingHeader from '@/components/briefing/BriefingHeader.vue';
import BriefingFeed from '@/components/briefing/BriefingFeed.vue';

const store = useBriefingStore();

onLoad(async () => {
  await store.loadToday();
});

onPullDownRefresh(async () => {
  await store.refresh();
  uni.stopPullDownRefresh();
});

const dateLabel = computed(() => {
  if (!store.feed) return '';
  const d = new Date(store.feed.biz_date);
  const weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  return `${store.feed.biz_date.substring(5)} ${weekdays[d.getDay()]}`;
});

import { t } from '@/i18n';
function goHistory() { uni.navigateTo({ url: '/pages/ai-briefing/history' }); }
function goLayout() { uni.navigateTo({ url: '/pages/ai-briefing/layout-setting' }); }
</script>

<template>
  <view class="page">
    <BriefingHeader :date="dateLabel" :user-name="store.feed?.user?.role === 'OWNER' ? '张总' : ''" />

    <view v-if="store.error" class="banner">{{ store.error }}</view>

    <view v-if="store.loading" class="loading">加载中…</view>

    <BriefingFeed
      v-else-if="store.feed"
      :cards="store.feed.cards"
      @ignore="(id: number) => store.ignore(id)"
      @feedback="(id: number, v: 'UP'|'DOWN') => store.feedback(id, v)"
    />

    <view class="footer">
      <text class="more" @tap="goHistory">{{ t('briefing.history') }} ›</text>
      <text class="more" @tap="goLayout">{{ t('briefing.settings') }}</text>
    </view>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding-bottom: 60rpx; }
.banner { background: #fff8eb; color: #e6a23c; padding: 16rpx 32rpx; font-size: 24rpx; }
.loading { text-align: center; padding: 80rpx 0; color: #909399; }
.footer { display: flex; justify-content: space-between; padding: 32rpx; }
.more { color: #1989fa; font-size: 26rpx; }
</style>
