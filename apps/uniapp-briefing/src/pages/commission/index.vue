<template>
  <view class="page">
    <view class="hd">
      <text class="title">我的提成</text>
      <text class="subtitle">{{ period }}</text>
    </view>

    <view class="summary">
      <view class="kv"><text class="k">本月计提</text><text class="v primary">¥{{ fmt(result.commission_final) }}</text></view>
      <view class="kv"><text class="k">挂牌毛利</text><text class="v">¥{{ fmt(result.gross_profit_listed) }}</text></view>
      <view class="kv"><text class="k">销售吨数</text><text class="v">{{ result.tonnage }} 吨</text></view>
    </view>

    <view class="card">
      <view class="card-title">扣减明细</view>
      <view class="row"><text>应收占款扣息</text><text>¥{{ fmt(result.ar_interest_amt) }}</text></view>
      <view class="row"><text>库存占款扣息</text><text>¥{{ fmt(result.inv_interest_amt) }}</text></view>
      <view class="row"><text>预付款扣息</text><text>¥{{ fmt(result.prepay_interest_amt) }}</text></view>
      <view class="row"><text>业务费扣减</text><text>¥{{ fmt(result.biz_fee_amt) }}</text></view>
      <view class="row"><text>抹零扣减</text><text>¥{{ fmt(result.roundoff_amt) }}</text></view>
    </view>

    <view class="card">
      <view class="card-title">规则命中明细 ({{ result.line_details?.length || 0 }} 条)</view>
      <view v-for="d in result.line_details" :key="d.order_no" class="line">
        <text class="ln">#{{ d.order_no }}</text>
        <text class="lbl">{{ d.matched_rule_label }}</text>
        <text class="rate">{{ (d.rate * 100).toFixed(1) }}%</text>
        <text class="amt">¥{{ fmt(d.raw_commission) }}</text>
      </view>
    </view>

    <view class="card explain">
      <view class="card-title">计算说明</view>
      <view v-for="(t, i) in result.explain_trace" :key="i" class="step">
        <text class="dot">·</text><text>{{ t }}</text>
      </view>
    </view>

    <view class="footer">
      <text class="hint">如有疑问, 请联系销售总监 / 财务对账.</text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { commissionApi, demoTemplates } from '@/services/commission';

const period = ref(new Date().toISOString().slice(0, 7));
const result = ref<any>({
  commission_final: 0,
  gross_profit_listed: 0,
  tonnage: 0,
  ar_interest_amt: 0, inv_interest_amt: 0, prepay_interest_amt: 0,
  biz_fee_amt: 0, roundoff_amt: 0,
  line_details: [],
  explain_trace: [],
});

function fmt(n: number | undefined) {
  if (n == null) return '0.00';
  return n.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
}

onMounted(async () => {
  try {
    const demoOrders = [
      { order_no: 'SO001', order_date: '2026-05-01', rep_id: 100, customer_id: 1,
        customer_seg: 'PROFIT', sales_mode: 'DIRECT', settle_type: 'CASH',
        tonnage: 100, revenue: 400000, listed_gross_profit: 20000, ton_gross_profit: 200,
        avg_ar_balance: 800000 },
      { order_no: 'SO002', order_date: '2026-05-05', rep_id: 100, customer_id: 2,
        customer_seg: 'VOLUME', sales_mode: 'DIRECT', settle_type: 'T+30',
        tonnage: 200, revenue: 800000, listed_gross_profit: 20000, ton_gross_profit: 100 },
    ];
    const res = await commissionApi.calcByTemplate({
      business_line: 'TRADE', tenant_id: 1, period_month: period.value,
      rep_id: 100, rep_name: '张三', orders: demoOrders,
    });
    result.value = res.result;
  } catch (e) {
    console.warn('commission api unavailable, using demo', e);
    result.value = {
      commission_final: 12150,
      gross_profit_listed: 40000,
      tonnage: 300,
      ar_interest_amt: 3000, inv_interest_amt: 1500, prepay_interest_amt: 0,
      biz_fee_amt: 200, roundoff_amt: 50,
      line_details: [
        { order_no: 'SO001', matched_rule_label: '直销+现款+利润型', rate: 0.35, raw_commission: 8400 },
        { order_no: 'SO002', matched_rule_label: '直销+走量型', rate: 0.25, raw_commission: 4000 },
      ],
      explain_trace: [
        '方案=TPL_TRADE_GP30(【模板】钢贸-按挂牌毛利30%), 基数类型=LISTED_GROSS_PROFIT, 默认系数=0.3',
        '原始提成总额=12400.00, 应收利息扣减=3000.00, 库存利息=1500.00, 预付利息=0.00, 业务费扣=200.00, 抹零扣=50.00',
      ],
    };
  }
});
</script>

<style lang="scss" scoped>
.page { padding: 24rpx; background: #f5f6f8; min-height: 100vh; }
.hd { padding: 24rpx; .title { font-size: 36rpx; font-weight: 700; } .subtitle { font-size: 24rpx; color: #888; margin-left: 16rpx; } }
.summary { background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 16rpx;
  .kv { display: flex; justify-content: space-between; padding: 8rpx 0; }
  .v.primary { color: #d4380d; font-weight: 700; font-size: 32rpx; }
}
.card { background: #fff; border-radius: 12rpx; padding: 24rpx; margin-bottom: 16rpx;
  .card-title { font-weight: 700; margin-bottom: 12rpx; }
  .row { display: flex; justify-content: space-between; padding: 6rpx 0; font-size: 26rpx; }
  .line { display: flex; gap: 12rpx; font-size: 24rpx; padding: 6rpx 0; align-items: center;
    .ln { color: #1677ff; }
    .lbl { flex: 1; color: #555; }
    .rate { color: #666; }
    .amt { color: #d4380d; font-weight: 600; }
  }
  &.explain .step { font-size: 22rpx; color: #555; padding: 4rpx 0;
    .dot { margin-right: 8rpx; color: #aaa; }
  }
}
.footer { text-align: center; padding: 24rpx; .hint { font-size: 22rpx; color: #aaa; } }
</style>
