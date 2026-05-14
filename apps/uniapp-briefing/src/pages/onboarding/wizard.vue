<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { onLoad } from '@dcloudio/uni-app';
import {
  onboardingApi, BUSINESS_LINES, ROLES_BY_BIZ, INTERESTS_BY_ROLE, ALL_INTERESTS
} from '@/services/onboarding';

const step = ref(1);
const total = 3;
const submitting = ref(false);

const bizLine = ref<string>('');
const role = ref<string>('');
const interests = ref<string[]>([]);
const recommendedPack = ref<any>(null);

const availableRoles = computed(() => ROLES_BY_BIZ[bizLine.value] || []);

onLoad(async () => {
  // 已 onboarding 过则跳过
  try {
    const p = await onboardingApi.getPreferences();
    if (p?.onboarding_done) {
      uni.reLaunch({ url: '/pages/ai-briefing/index' });
    }
  } catch {}
});

function pickBiz(code: string) {
  bizLine.value = code;
  role.value = '';
  interests.value = [];
}

function pickRole(code: string) {
  role.value = code;
  // 自动勾选该角色的默认关注
  interests.value = (INTERESTS_BY_ROLE[code] || []).slice();
  // 提前预览推荐包
  onboardingApi.recommendPack(bizLine.value, code).then(r => {
    recommendedPack.value = r.primary;
  }).catch(() => {
    recommendedPack.value = {
      pack_id: `PK_${bizLine.value}_${code}`,
      name: '默认包',
      metric_count: 12,
    };
  });
}

function toggleInterest(it: string) {
  const i = interests.value.indexOf(it);
  if (i >= 0) interests.value.splice(i, 1);
  else interests.value.push(it);
}

function next() {
  if (step.value === 1 && !bizLine.value) {
    uni.showToast({ title: '请选择业务类型', icon: 'none' }); return;
  }
  if (step.value === 2 && !role.value) {
    uni.showToast({ title: '请选择岗位', icon: 'none' }); return;
  }
  step.value++;
}

function prev() {
  if (step.value > 1) step.value--;
}

async function finish() {
  submitting.value = true;
  try {
    await onboardingApi.savePreferences({
      business_line: bizLine.value,
      primary_role: role.value,
      interests: interests.value,
    });
    uni.showToast({ title: '设置完成! 欢迎使用', icon: 'success' });
    setTimeout(() => uni.reLaunch({ url: '/pages/ai-briefing/index' }), 1000);
  } catch (e: any) {
    uni.showToast({ title: '保存失败, 请重试', icon: 'error' });
  } finally {
    submitting.value = false;
  }
}

function tryQuestion() {
  uni.navigateTo({
    url: '/pages/ai/chat?prefillText=' + encodeURIComponent('我本月销售额'),
  });
}
</script>

<template>
  <view class="page">
    <view class="header">
      <text class="title">欢迎使用 钢铁 AI 经营分析平台 ✨</text>
      <view class="progress">
        <view v-for="i in total" :key="i"
              :class="['dot', i <= step ? 'active' : '']" />
      </view>
      <text class="step-info">Step {{ step }} / {{ total }}</text>
    </view>

    <!-- ============ Step 1: 业务类型 ============ -->
    <view v-if="step === 1" class="content">
      <view class="step-title">您的企业属于哪种业务?</view>
      <view class="step-desc">选择业务类型, 我们会为你过滤不相关的指标</view>
      <view class="biz-list">
        <view v-for="b in BUSINESS_LINES" :key="b.code"
              :class="['biz-card', bizLine === b.code ? 'on' : '']"
              @tap="pickBiz(b.code)">
          <text class="icon">{{ b.icon }}</text>
          <text class="name">{{ b.name }}</text>
          <text class="desc">{{ b.desc }}</text>
        </view>
      </view>
    </view>

    <!-- ============ Step 2: 岗位 ============ -->
    <view v-else-if="step === 2" class="content">
      <view class="step-title">您的岗位是?</view>
      <view class="step-desc">不同岗位看到的指标不同, 老板看全部, 业务员只看销售</view>
      <view class="role-grid">
        <view v-for="r in availableRoles" :key="r.code"
              :class="['role-card', role === r.code ? 'on' : '']"
              @tap="pickRole(r.code)">
          <text class="emoji">{{ r.emoji }}</text>
          <text class="name">{{ r.name }}</text>
        </view>
      </view>
      <view v-if="recommendedPack" class="pack-preview">
        <text class="hint">📦 我们将为你订阅:</text>
        <text class="pack-name">{{ recommendedPack.name }}</text>
        <text class="pack-meta">含 {{ recommendedPack.metric_count }} 个核心指标</text>
      </view>
    </view>

    <!-- ============ Step 3: 关注领域 ============ -->
    <view v-else-if="step === 3" class="content">
      <view class="step-title">您最关心什么?</view>
      <view class="step-desc">已根据您的岗位推荐勾选, 可手动调整 (多选)</view>
      <view class="interest-grid">
        <view v-for="it in ALL_INTERESTS" :key="it"
              :class="['interest-chip', interests.includes(it) ? 'on' : '']"
              @tap="toggleInterest(it)">{{ it }}</view>
      </view>
      <view class="summary-card">
        <view class="line"><text class="lbl">业务类型:</text> <text>{{ BUSINESS_LINES.find(b => b.code === bizLine)?.name }}</text></view>
        <view class="line"><text class="lbl">岗位:</text> <text>{{ availableRoles.find(r => r.code === role)?.name }}</text></view>
        <view class="line"><text class="lbl">关注 {{ interests.length }} 项:</text></view>
        <view class="tag-row">
          <text v-for="it in interests" :key="it" class="tag">{{ it }}</text>
        </view>
      </view>
    </view>

    <!-- ============ 底部操作 ============ -->
    <view class="bottom">
      <button v-if="step > 1" class="btn-prev" @tap="prev">上一步</button>
      <button v-if="step < total" class="btn-next" @tap="next">下一步 →</button>
      <button v-else class="btn-finish" :loading="submitting" @tap="finish">开始使用 ✓</button>
    </view>

    <!-- 完成页可见 -->
    <view v-if="step === total" class="try-tip" @tap="tryQuestion">
      💡 完成后试问一个问题: "我本月销售额"
    </view>
  </view>
</template>

<style>
.page { background: linear-gradient(180deg, #ecf5ff 0%, #f5f7fa 60%); min-height: 100vh; padding: 32rpx; }
.header { text-align: center; padding: 24rpx 0; }
.title { font-size: 36rpx; font-weight: 700; color: #1f2937; }
.progress { display: flex; justify-content: center; gap: 16rpx; margin: 24rpx 0 8rpx; }
.dot { width: 24rpx; height: 8rpx; border-radius: 4rpx; background: #d4dbe5; }
.dot.active { background: #1989fa; width: 48rpx; }
.step-info { color: #909399; font-size: 24rpx; }

.content { background: #fff; border-radius: 24rpx; padding: 32rpx; margin: 24rpx 0; box-shadow: 0 4rpx 24rpx rgba(0,0,0,.06); }
.step-title { font-size: 32rpx; font-weight: 600; color: #1f2937; }
.step-desc { font-size: 24rpx; color: #909399; margin: 8rpx 0 24rpx; }

.biz-list { display: flex; flex-direction: column; gap: 16rpx; }
.biz-card { padding: 24rpx; border: 2rpx solid #ebeef5; border-radius: 16rpx; display: flex; flex-direction: column; }
.biz-card.on { border-color: #1989fa; background: #ecf5ff; }
.biz-card .icon { font-size: 48rpx; }
.biz-card .name { font-size: 30rpx; font-weight: 600; color: #1f2937; margin: 8rpx 0; }
.biz-card .desc { font-size: 22rpx; color: #6b7280; }

.role-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16rpx; }
.role-card { padding: 20rpx; border: 2rpx solid #ebeef5; border-radius: 16rpx; text-align: center; }
.role-card.on { border-color: #1989fa; background: #ecf5ff; }
.role-card .emoji { font-size: 40rpx; }
.role-card .name { font-size: 26rpx; color: #1f2937; }

.pack-preview { background: #f0f9ff; border-radius: 12rpx; padding: 16rpx; margin-top: 24rpx; }
.pack-preview .hint { font-size: 22rpx; color: #909399; }
.pack-preview .pack-name { font-size: 28rpx; font-weight: 600; color: #1989fa; margin-top: 4rpx; }
.pack-preview .pack-meta { font-size: 22rpx; color: #6b7280; }

.interest-grid { display: flex; flex-wrap: wrap; gap: 12rpx; }
.interest-chip { padding: 12rpx 24rpx; border: 2rpx solid #ebeef5; border-radius: 32rpx; font-size: 24rpx; color: #6b7280; }
.interest-chip.on { border-color: #1989fa; color: #1989fa; background: #ecf5ff; }

.summary-card { background: #f5f7fa; border-radius: 12rpx; padding: 24rpx; margin-top: 24rpx; }
.summary-card .line { padding: 6rpx 0; font-size: 26rpx; color: #1f2937; }
.summary-card .lbl { color: #909399; font-size: 22rpx; margin-right: 8rpx; }
.tag-row { display: flex; flex-wrap: wrap; gap: 8rpx; margin-top: 8rpx; }
.tag { background: #ecf5ff; color: #1989fa; padding: 4rpx 12rpx; border-radius: 8rpx; font-size: 22rpx; }

.bottom { display: flex; gap: 16rpx; margin-top: 32rpx; }
.btn-prev, .btn-next, .btn-finish {
  flex: 1; font-size: 28rpx; border-radius: 32rpx;
}
.btn-prev { background: #f5f7fa; color: #6b7280; }
.btn-next { background: #1989fa; color: #fff; }
.btn-finish { background: #67c23a; color: #fff; }
.btn-prev::after, .btn-next::after, .btn-finish::after { border: none; }

.try-tip { margin-top: 16rpx; padding: 16rpx; background: #fff8e6; color: #e6a23c; font-size: 24rpx; border-radius: 12rpx; text-align: center; }
</style>
