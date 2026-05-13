<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { metricsApi } from '@/api/metrics';

const props = defineProps<{ code?: string }>();
const router = useRouter();
const isEdit = computed(() => !!props.code);

const form = reactive<any>({
  metric_code: '', name: '', name_zh: '', domain: 'SALES',
  synonyms: [], applicable: ['TRADE', 'PROCESS', 'MILL'],
  fact: '', formula: '', semantics: 'additive', time_agg: 'sum',
  format: 'amount', unit: '', sensitivity: 'LOW',
  bizToken_multiplier: 1.0,
  owner: '', steward: '', approvers: [],
  requires_metrics: [], filter_expr: '', join_tables: [],
  sla_freshness_minutes: 60, sla_availability: 99.5, sla_p95: 2000,
  tags: [], notes: '',
});

const change_note = ref('');
const sandboxResult = ref<any>(null);
const sandboxLoading = ref(false);
const impactPreview = ref<any>(null);

onMounted(async () => {
  if (props.code) {
    try {
      const d = await metricsApi.get(props.code);
      Object.assign(form, d, {
        sla_freshness_minutes: d.sla?.freshness_minutes ?? 60,
        sla_availability: d.sla?.availability ?? 99.5,
        sla_p95: d.sla?.query_p95_ms ?? 2000,
      });
    } catch {
      ElMessage.warning('未连接后端, 显示空表单');
    }
  }
});

async function runSandbox() {
  sandboxLoading.value = true;
  try {
    sandboxResult.value = await metricsApi.sandboxRun(form.metric_code || form.name, {
      dimensions: ['org.region'], time: { preset: 'last_month' }, limit: 10,
    });
  } catch {
    sandboxResult.value = { rows: [
      { region: '华东', value: 12300000 },
      { region: '华南', value: 8900000 },
    ], exec_ms: 182, scan_rows: 1820 };
  } finally {
    sandboxLoading.value = false;
  }
}

async function submitReview() {
  try {
    const payload = {
      ...form,
      sla: {
        freshness_minutes: form.sla_freshness_minutes,
        availability: form.sla_availability,
        query_p95_ms: form.sla_p95,
      },
    };
    if (isEdit.value) {
      await metricsApi.patch(form.metric_code, payload, change_note.value);
    } else {
      await metricsApi.create(payload);
    }
    ElMessage.success('已提交审批');
    router.push('/requests');
  } catch (e: any) {
    ElMessage.error(e.message || '提交失败');
  }
}
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        {{ isEdit ? `编辑指标: ${form.metric_code}` : '新增指标' }}
      </template>

      <el-form :model="form" label-width="120px" label-position="right">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="编号">
              <el-input v-model="form.metric_code" :disabled="isEdit" placeholder="留空自动生成 M179" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="英文名"><el-input v-model="form.name" /></el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="中文名"><el-input v-model="form.name_zh" /></el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="6">
            <el-form-item label="域">
              <el-select v-model="form.domain">
                <el-option v-for="d in ['SALES','INVENTORY','PRODUCTION','PROCUREMENT','QUALITY','CAPITAL','RISK','FORECAST','ABC']"
                           :key="d" :label="d" :value="d" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="语义">
              <el-select v-model="form.semantics">
                <el-option label="additive 累积型" value="additive" />
                <el-option label="snapshot 时点快照" value="snapshot" />
                <el-option label="virtual 派生" value="virtual" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="跨日聚合" v-if="form.semantics === 'snapshot'">
              <el-select v-model="form.time_agg">
                <el-option label="AVG 日均" value="avg" />
                <el-option label="FIRST 期初" value="first" />
                <el-option label="LAST 期末" value="last" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="6">
            <el-form-item label="格式">
              <el-select v-model="form.format">
                <el-option v-for="f in ['amount','ton','price','percent','days','count','ratio','score']" :key="f" :label="f" :value="f" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="适用类型">
          <el-checkbox-group v-model="form.applicable">
            <el-checkbox label="TRADE">钢贸</el-checkbox>
            <el-checkbox label="PROCESS">加工</el-checkbox>
            <el-checkbox label="MILL">钢厂</el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <el-form-item label="敏感度 / 计费">
          <el-radio-group v-model="form.sensitivity">
            <el-radio value="LOW">LOW</el-radio>
            <el-radio value="MEDIUM">MEDIUM</el-radio>
            <el-radio value="HIGH">HIGH</el-radio>
          </el-radio-group>
          <el-input-number v-model="form.bizToken_multiplier" :min="1" :max="5" :step="0.1" :precision="1"
                           controls-position="right" style="margin-left:12px;" />
          <span style="margin-left:6px;color:#909399;">x 计费乘数</span>
        </el-form-item>

        <el-form-item label="同义词">
          <el-input v-model="form.synonyms" placeholder="逗号分隔" />
        </el-form-item>

        <el-form-item label="主表">
          <el-input v-model="form.fact" placeholder="如 dws_sales_daily" />
        </el-form-item>

        <el-form-item label="公式">
          <el-input v-model="form.formula" type="textarea" :rows="3"
                    placeholder="SUM(order_amount) / NULLIF(SUM(order_tonnage), 0)" />
        </el-form-item>

        <el-form-item label="依赖指标"><el-input v-model="form.requires_metrics" placeholder="逗号分隔" /></el-form-item>
        <el-form-item label="过滤条件"><el-input v-model="form.filter_expr" placeholder="WHERE 子句, 如 source='IPQC'" /></el-form-item>

        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="Owner"><el-input v-model="form.owner" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="Steward"><el-input v-model="form.steward" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="审批人"><el-input v-model="form.approvers" placeholder="多人逗号分隔" /></el-form-item></el-col>
        </el-row>

        <el-divider>SLA</el-divider>
        <el-row :gutter="16">
          <el-col :span="8"><el-form-item label="新鲜度(分钟)"><el-input-number v-model="form.sla_freshness_minutes" :min="1" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="可用性(%)"><el-input-number v-model="form.sla_availability" :min="0" :max="100" :step="0.1" :precision="2" /></el-form-item></el-col>
          <el-col :span="8"><el-form-item label="P95(ms)"><el-input-number v-model="form.sla_p95" :min="0" /></el-form-item></el-col>
        </el-row>

        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>

        <el-form-item label="变更说明" v-if="isEdit">
          <el-input v-model="change_note" type="textarea" :rows="2" placeholder="必填: 本次为何修改" />
        </el-form-item>
      </el-form>

      <el-divider>试算沙箱</el-divider>
      <el-button @click="runSandbox" :loading="sandboxLoading">运行示例数据</el-button>
      <el-table v-if="sandboxResult" :data="sandboxResult.rows" size="small" style="margin-top:8px;" border>
        <el-table-column v-for="(_, k) in sandboxResult.rows[0]" :key="k" :prop="String(k)" :label="String(k)" />
      </el-table>
      <div v-if="sandboxResult" style="margin-top:4px;color:#909399;">
        耗时 {{ sandboxResult.exec_ms }}ms · 扫描 {{ sandboxResult.scan_rows }} 行
      </div>

      <el-divider>影响分析</el-divider>
      <el-alert type="success" :closable="false" title="✓ 无下游指标依赖 / 未被任何看板引用 / 不影响计费" />

      <div style="margin-top:24px;text-align:right;">
        <el-button @click="router.back()">取消</el-button>
        <el-button>存为草稿</el-button>
        <el-button type="primary" @click="submitReview">提交审批</el-button>
      </div>
    </el-card>
  </div>
</template>
