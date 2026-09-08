<script setup lang="ts">
import { ref } from 'vue';

const cards = ref([
  { type: 'SUMMARY', label: '每日摘要', enabled: true },
  { type: 'RISK', label: '风险预警', enabled: true },
  { type: 'ADVICE', label: 'AI 建议', enabled: true },
  { type: 'CAPITAL', label: '资金占用', enabled: true },
  { type: 'FORECAST', label: '预测', enabled: true },
  { type: 'ABC', label: 'ABC 周报', enabled: true },
  { type: 'INSIGHT', label: '异常洞察', enabled: true },
  { type: 'RECOMMEND', label: '推荐问题', enabled: false },
  { type: 'BALANCE', label: '余额提醒', enabled: true },
]);

const silenceFrom = ref('22:00');
const silenceTo = ref('08:00');

const channels = ref({
  HIGH: ['INAPP', 'WECOM'],
  CRITICAL: ['INAPP', 'WECOM', 'SMS'],
});

function save() {
  uni.showLoading({ title: '保存中…' });
  setTimeout(() => {
    uni.hideLoading();
    uni.showToast({ title: '已保存', icon: 'success' });
  }, 600);
}
</script>

<template>
  <view class="page">
    <view class="block">
      <view class="b-title">显示的卡片类型</view>
      <view v-for="c in cards" :key="c.type" class="row">
        <text class="lbl">{{ c.label }}</text>
        <switch :checked="c.enabled" @change="(e: any) => c.enabled = e.detail.value" />
      </view>
    </view>

    <view class="block">
      <view class="b-title">免打扰时段</view>
      <view class="row">
        <text class="lbl">从</text>
        <text class="val">{{ silenceFrom }}</text>
      </view>
      <view class="row">
        <text class="lbl">至</text>
        <text class="val">{{ silenceTo }}</text>
      </view>
    </view>

    <view class="block">
      <view class="b-title">推送渠道</view>
      <view class="row">
        <text class="lbl">HIGH</text>
        <text class="val">{{ channels.HIGH.join(' / ') }}</text>
      </view>
      <view class="row">
        <text class="lbl">CRITICAL</text>
        <text class="val">{{ channels.CRITICAL.join(' / ') }}</text>
      </view>
    </view>

    <button class="save" @tap="save">保存</button>
  </view>
</template>

<style>
.page { background: #f5f7fa; min-height: 100vh; padding: 16rpx; }
.block { background: #fff; border-radius: 16rpx; margin-bottom: 16rpx; }
.b-title { padding: 16rpx 32rpx; font-size: 24rpx; color: #909399; border-bottom: 1rpx solid #f0f0f0; }
.row { display: flex; align-items: center; padding: 20rpx 32rpx; border-bottom: 1rpx solid #f0f0f0; }
.row .lbl { flex: 1; font-size: 28rpx; }
.row .val { color: #909399; font-size: 26rpx; }
.save { margin: 32rpx; background: #1989fa; color: #fff; }
</style>
