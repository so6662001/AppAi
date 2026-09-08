<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage, ElMessageBox } from 'element-plus';
import { changeApi } from '@/api/metrics';

const props = defineProps<{ id: string }>();
const router = useRouter();
const data = ref<any>(null);

onMounted(async () => {
  try {
    data.value = await changeApi.get(Number(props.id));
  } catch {
    data.value = {
      request_id: 128,
      metric_code: 'net_profit',
      change_type: 'FORMULA',
      from_version: '1.0.0', to_version: '2.0.0',
      created_by: 'zhang.san',
      status: 'SUBMITTED',
      diff: {
        formula: { old: 'contribution_margin', new: 'contribution_margin - allocated_period_expense' },
        note:    { old: '直接经营毛利', new: '= 贡献毛利 - 期间费用分摊' },
      },
      impact_summary: {
        downstream_metrics: ['net_margin', 'ton_net_profit'],
        dashboards: ['老板驾驶舱', '财务月报', '客户级 IRR 看板', '...'],
        saved_queries: [],
        ai_sessions_7d: 148,
        billing_rules: [],
        subscribers_count: 12,
        risk_level: 'HIGH',
        recommended_approvers: ['cfo@steel-erp.com', 'compliance@steel-erp.com'],
      },
      sample_diff: { period: '2026-04', region: '华东', old: 1820000, new: 880000, delta_pct: -0.52 },
    };
  }
});

async function approve() {
  await ElMessageBox.prompt('审批意见', '通过', { confirmButtonText: '通过', cancelButtonText: '取消' });
  await changeApi.approve(Number(props.id));
  ElMessage.success('已通过');
  router.push('/requests');
}
async function reject() {
  const { value } = await ElMessageBox.prompt('打回原因 (必填)', '打回', {
    inputValidator: v => !!v || '必填',
  });
  await changeApi.reject(Number(props.id), value);
  ElMessage.success('已打回');
  router.push('/requests');
}
</script>

<template>
  <div class="page" v-if="data">
    <el-page-header @back="router.back()">
      <template #content>
        变更 #{{ data.request_id }} · {{ data.metric_code }}
        <el-tag style="margin-left:8px;">{{ data.change_type }}</el-tag>
        <el-tag style="margin-left:4px;" type="warning">{{ data.status }}</el-tag>
      </template>
      <template #extra>
        <el-button type="primary" @click="approve">通过</el-button>
        <el-button type="danger" plain @click="reject">打回</el-button>
      </template>
    </el-page-header>

    <el-row :gutter="16" style="margin-top:16px;">
      <el-col :span="12">
        <el-card>
          <template #header>差异 Diff (v{{ data.from_version }} → v{{ data.to_version }})</template>
          <pre class="sql-preview" v-for="(v, k) in data.diff" :key="k">
{{ k }}:
- {{ v.old }}
+ {{ v.new }}</pre>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            影响分析
            <el-tag :type="data.impact_summary.risk_level === 'HIGH' ? 'danger' : 'warning'" style="margin-left:8px;">
              {{ data.impact_summary.risk_level }}
            </el-tag>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="下游指标 ({{ data.impact_summary.downstream_metrics.length }})">
              <el-tag v-for="m in data.impact_summary.downstream_metrics" :key="m" size="small" style="margin-right:4px;">{{ m }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="看板引用 ({{ data.impact_summary.dashboards.length }})">
              {{ data.impact_summary.dashboards.slice(0, 5).join(' / ') }}{{ data.impact_summary.dashboards.length > 5 ? ' ...' : '' }}
            </el-descriptions-item>
            <el-descriptions-item label="近 7 天 AI 会话">{{ data.impact_summary.ai_sessions_7d }} 次</el-descriptions-item>
            <el-descriptions-item label="计费规则影响">{{ data.impact_summary.billing_rules.length === 0 ? '无' : data.impact_summary.billing_rules.join(', ') }}</el-descriptions-item>
            <el-descriptions-item label="订阅者">{{ data.impact_summary.subscribers_count }} 人 (将在合并后收到通知)</el-descriptions-item>
            <el-descriptions-item label="推荐审批人">
              <el-tag v-for="a in data.impact_summary.recommended_approvers" :key="a" type="info" size="small" style="margin-right:4px;">{{ a }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top:16px;" v-if="data.sample_diff">
      <template #header>试算对比 (样例: {{ data.sample_diff.period }} × {{ data.sample_diff.region }})</template>
      <el-row :gutter="16">
        <el-col :span="8"><el-statistic title="旧值" :value="data.sample_diff.old" /></el-col>
        <el-col :span="8"><el-statistic title="新值" :value="data.sample_diff.new" /></el-col>
        <el-col :span="8"><el-statistic title="差异" :value="(data.sample_diff.delta_pct * 100).toFixed(1) + '%'" /></el-col>
      </el-row>
    </el-card>
  </div>
</template>
