<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue';
import { useRouter } from 'vue-router';
import { metricsApi, ListParams } from '@/api/metrics';
import type { MetricSummary } from '@/api/index';

const router = useRouter();
const loading = ref(false);
const list = ref<MetricSummary[]>([]);
const total = ref(0);

const filter = reactive<ListParams>({
  q: '', domain: '', status: '', sensitivity: '',
  applicable: [], owner: '', page: 1, size: 30,
});

const domainOptions = [
  'SALES', 'INVENTORY', 'PRODUCTION', 'PROCUREMENT', 'QUALITY',
  'CAPITAL', 'RISK', 'FORECAST', 'ABC',
];

async function fetchData() {
  loading.value = true;
  try {
    const data = await metricsApi.list(filter);
    list.value = data.items;
    total.value = data.total;
  } catch {
    // 演示数据
    list.value = sampleMetrics();
    total.value = list.value.length;
  } finally {
    loading.value = false;
  }
}

function sampleMetrics(): MetricSummary[] {
  return [
    { metric_code: 'M001', name: 'sales_amount', name_zh: '销售额', domain: 'SALES', version: '3.2.0', status: 'PUBLISHED', sensitivity: 'MEDIUM', owner: '张三', sla_health: 'HEALTHY', call_count_7d: 12340 },
    { metric_code: 'M006', name: 'gross_profit', name_zh: '销售毛利', domain: 'SALES', version: '2.1.0', status: 'PUBLISHED', sensitivity: 'HIGH', owner: '张三', sla_health: 'HEALTHY', call_count_7d: 8920 },
    { metric_code: 'M102', name: 'listed_gross_profit', name_zh: '挂价毛利', domain: 'SALES', version: '1.0.0', status: 'PUBLISHED', sensitivity: 'HIGH', owner: '张三', sla_health: 'AT_RISK', call_count_7d: 3210 },
    { metric_code: 'M120', name: 'net_profit', name_zh: '销售净利润', domain: 'SALES', version: '2.0.0', status: 'PUBLISHED', sensitivity: 'HIGH', owner: 'CFO', sla_health: 'HEALTHY', call_count_7d: 1180 },
    { metric_code: 'M131', name: 'inv_turnover_ratio_by_tonnage', name_zh: '存货周转率(按吨)', domain: 'INVENTORY', version: '1.0.0', status: 'PUBLISHED', sensitivity: 'LOW', owner: '李四', sla_health: 'HEALTHY', call_count_7d: 2340 },
    { metric_code: 'M139', name: 'customer_irr', name_zh: '客户IRR', domain: 'CAPITAL', version: '1.0.0', status: 'PUBLISHED', sensitivity: 'HIGH', owner: 'CFO', sla_health: 'HEALTHY', call_count_7d: 320 },
    { metric_code: 'M147', name: 'hedge_net_exposure', name_zh: '套保净敞口', domain: 'RISK', version: '1.0.0', status: 'PUBLISHED', sensitivity: 'HIGH', owner: '财务总监', sla_health: 'HEALTHY', call_count_7d: 180 },
    { metric_code: 'M060', name: 'oee', name_zh: 'OEE', domain: 'PRODUCTION', version: '1.0.0', status: 'PUBLISHED', sensitivity: 'LOW', owner: '生产总监', sla_health: 'AT_RISK', call_count_7d: 1620 },
  ];
}

function statusTag(s: string) {
  if (s === 'PUBLISHED') return 'success';
  if (s === 'DRAFT') return 'info';
  if (s === 'REVIEW') return 'warning';
  if (s === 'DEPRECATED') return 'danger';
  return '';
}
function sensTag(s: string) {
  if (s === 'HIGH') return 'danger';
  if (s === 'MEDIUM') return 'warning';
  return 'info';
}
function slaTag(h?: string) {
  if (h === 'HEALTHY') return 'success';
  if (h === 'AT_RISK') return 'warning';
  if (h === 'FAILING') return 'danger';
  return 'info';
}

function viewDetail(row: MetricSummary) { router.push(`/metrics/${row.metric_code}`); }
function editMetric(row: MetricSummary) { router.push(`/metrics/${row.metric_code}/edit`); }

onMounted(fetchData);
watch(() => [filter.q, filter.domain, filter.status, filter.sensitivity, filter.owner, filter.page], fetchData, { deep: true });
</script>

<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-select v-model="filter.domain" placeholder="域" clearable style="width:120px;">
          <el-option v-for="d in domainOptions" :key="d" :label="d" :value="d" />
        </el-select>
        <el-select v-model="filter.status" placeholder="状态" clearable style="width:140px;">
          <el-option label="PUBLISHED" value="PUBLISHED" />
          <el-option label="DRAFT" value="DRAFT" />
          <el-option label="REVIEW" value="REVIEW" />
          <el-option label="DEPRECATED" value="DEPRECATED" />
        </el-select>
        <el-select v-model="filter.sensitivity" placeholder="敏感度" clearable style="width:120px;">
          <el-option label="LOW" value="LOW" />
          <el-option label="MEDIUM" value="MEDIUM" />
          <el-option label="HIGH" value="HIGH" />
        </el-select>
        <el-checkbox-group v-model="filter.applicable">
          <el-checkbox label="TRADE">钢贸</el-checkbox>
          <el-checkbox label="PROCESS">加工</el-checkbox>
          <el-checkbox label="MILL">钢厂</el-checkbox>
        </el-checkbox-group>
        <el-input v-model="filter.q" placeholder="搜索: 名称/编号/同义词/Owner" style="width:280px;" clearable />
        <div style="margin-left:auto;">
          <el-button type="primary" @click="router.push('/metrics/new')">+ 新增指标</el-button>
          <el-button>批量导出</el-button>
        </div>
      </div>

      <el-table :data="list" v-loading="loading" border size="default" highlight-current-row
                @row-dblclick="viewDetail">
        <el-table-column prop="metric_code" label="编号" width="100" sortable />
        <el-table-column label="名称" min-width="220">
          <template #default="{ row }">
            <div class="metric-label">{{ row.name_zh }}</div>
            <div class="metric-code">{{ row.name }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="domain" label="域" width="100" />
        <el-table-column prop="owner" label="Owner" width="100" />
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }"><el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="敏感度" width="90">
          <template #default="{ row }"><el-tag :type="sensTag(row.sensitivity)">{{ row.sensitivity }}</el-tag></template>
        </el-table-column>
        <el-table-column label="SLA" width="80">
          <template #default="{ row }"><el-tag :type="slaTag(row.sla_health)">{{ row.sla_health || '-' }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="call_count_7d" label="7d调用" width="90" align="right" sortable />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button link size="small" type="primary" @click="viewDetail(row)">查看</el-button>
            <el-button link size="small" @click="editMetric(row)">编辑</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="filter.page"
        v-model:page-size="filter.size"
        :total="total"
        :page-sizes="[20, 30, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background style="margin-top:12px;justify-content:flex-end;"
      />
    </el-card>
  </div>
</template>
