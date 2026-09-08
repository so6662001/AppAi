<script setup lang="ts">
defineProps<{ date: string; userName?: string }>();
</script>

<template>
  <view class="hd">
    <view class="greeting">
      <text class="welcome">早安{{ userName ? ', ' + userName : '' }} ☀️</text>
      <text class="date">{{ date }}</text>
    </view>
    <view class="badge">
      <text class="label">AI 经营助手</text>
    </view>
  </view>
</template>

<style scoped>
.hd { display: flex; justify-content: space-between; align-items: center; padding: 24rpx 32rpx 8rpx; }
.greeting { display: flex; flex-direction: column; }
.welcome { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.date { font-size: 22rpx; color: #909399; margin-top: 4rpx; }
.badge .label { font-size: 22rpx; color: #1989fa; padding: 4rpx 16rpx; background: #ecf5ff; border-radius: 16rpx; }
</style>
