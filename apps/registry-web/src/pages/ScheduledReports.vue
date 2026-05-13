<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { scheduledReportsApi, type ScheduledReport, type ReportRun } from '@/api/scheduled-report';

const list = ref<ScheduledReport[]>([]);
const loading = ref(false);
const filter = reactive({ status: '' });

const runDrawer = ref(false);
const runs = ref<ReportRun[]>([]);
const currentReport = ref<ScheduledReport | null>(null);

async function fetchData() {
  loading.value = true;
  try {
    const r = await scheduledReportsApi.list(filter);
    list.value = r.items;
  } catch {
    list.value = demo();
  } finally {
    loading.value = false;
  }
}

function demo(): ScheduledReport[] {
  return [
    { report_id: 1, name: '老板日报-销售&库存', description: '每日 08:00 推送昨日核心', status: 'ACTIVE',
      schedule_type: 'cron', cron_expr: '0 0 8 * * ?', channels: ['INAPP', 'WECOM'],
      next_run_at: '2026-05-14 08:00:00', last_run_at: '2026-05-13 08:00:00',
      fail_count: 0, source: 'template', user_id: 1,
      created_at: '2026-05-01', updated_at: '2026-05-01' },
    { report_id: 2, name: '上周华东达交率', description: '聊天另存', status: 'ACTIVE',
      schedule_type: 'weekly', cron_expr: '0 0 9 ? * MON', channels: ['INAPP'],
      next_run_at: '2026-05-19 09:00:00', last_run_at: '2026-05-12 09:00:00',
      fail_count: 0, source: 'chat', user_id: 1,
      created_at: '2026-05-10', updated_at: '2026-05-10' },
    { report_id: 3, name: 'A 类 SKU 缺货预警', status: 'PAUSED',
      schedule_type: 'daily', cron_expr: '0 0 7 * * ?', channels: ['INAPP', 'DINGTALK'],
      next_run_at: '2026-05-14 07:00:00', last_run_at: '2026-05-12 07:00:00',
      fail_count: 3, source: 'manual', user_id: 2,
      created_at: '2026-05-03', updated_at: '2026-05-12' },
  ];
}

async function viewRuns(row: ScheduledReport) {
  currentReport.value = row;
  runDrawer.value = true;
  try {
    runs.value = await scheduledReportsApi.runs(row.report_id, 30);
  } catch {
    runs.value = [
      { run_id: 1003, report_id: row.report_id, scheduled_at: '2026-05-13 08:00:00',
        finished_at: '2026-05-13 08:00:04', duration_ms: 3120, status: 'SUCCESS',
        rows_returned: 5, result_summary: '昨日销售 1,820 万', biz_tokens_charged: 1800 },
      { run_id: 1002, report_id: row.report_id, scheduled_at: '2026-05-12 08:00:00',
        finished_at: '2026-05-12 08:00:03', duration_ms: 2980, status: 'SUCCESS',
        rows_returned: 5, result_summary: '昨日销售 1,620 万', biz_tokens_charged: 1740 },
      { run_id: 1001, report_id: row.report_id, scheduled_at: '2026-05-11 08:00:00',
        status: 'FAILED', error_code: 'E_COST_EXCEEDED', error_msg: '扫描行数超限' },
    ] as any;
  }
}

async function togglePause(row: ScheduledReport) {
  try {
    if (row.status === 'ACTIVE') {
      await scheduledReportsApi.pause(row.report_id);
      row.status = 'PAUSED';
    } else {
      await scheduledReportsApi.resume(row.report_id);
      row.status = 'ACTIVE';
    }
    ElMessage.success(row.status === 'ACTIVE' ? '已启动' : '已暂停');
  } catch {
    ElMessage.error('操作失败');
  }
}

async function runNow(row: ScheduledReport) {
  try {
    const r = await scheduledReportsApi.runNow(row.report_id);
    ElMessage.success(`已提交 run #${r.run_id}`);
  } catch {
    ElMessage.error('触发失败');
  }
}

async function remove(row: ScheduledReport) {
  await ElMessageBox.confirm(`确认删除「${row.name}」?`, '删除', { type: 'warning' });
  try {
    await scheduledReportsApi.remove(row.report_id);
    list.value = list.value.filter(r => r.report_id !== row.report_id);
    ElMessage.success('已删除');
  } catch {
    ElMessage.error('失败');
  }
}

function statusTag(s: string) {
  if (s === 'ACTIVE') return 'success';
  if (s === 'PAUSED') return 'warning';
  if (s === 'EXPIRED') return 'info';
  return 'danger';
}
function runStatusTag(s: string) {
  if (s === 'SUCCESS') return 'success';
  if (s === 'FAILED') return 'danger';
  if (s === 'RUNNING') return 'primary';
  return 'info';
}

onMounted(fetchData);
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        <div style="display:flex;justify-content:space-between;align-items:center;">
          <span>定时报表 ({{ list.length }})</span>
          <div>
            <el-select v-model="filter.status" placeholder="状态" clearable size="small"
                       style="width:120px;" @change="fetchData">
              <el-option label="ACTIVE" value="ACTIVE" />
              <el-option label="PAUSED" value="PAUSED" />
              <el-option label="EXPIRED" value="EXPIRED" />
            </el-select>
            <el-button type="primary" size="small">+ 新建</el-button>
          </div>
        </div>
      </template>

      <el-table :data="list" v-loading="loading" border>
        <el-table-column label="名称" min-width="220">
          <template #default="{ row }">
            <div style="font-weight:600;">{{ row.name }}</div>
            <div style="color:#909399;font-size:12px;">{{ row.description || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="调度" width="180">
          <template #default="{ row }">
            <div>{{ row.schedule_type }}</div>
            <div style="color:#909399;font-size:12px;">{{ row.cron_expr || '—' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="渠道" width="160">
          <template #default="{ row }">
            <el-tag v-for="c in row.channels" :key="c" size="small" style="margin-right:4px;">{{ c }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="next_run_at" label="下次执行" width="160" />
        <el-table-column prop="last_run_at" label="上次执行" width="160" />
        <el-table-column label="失败" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.fail_count > 0" type="danger">{{ row.fail_count }}</el-tag>
            <span v-else>0</span>
          </template>
        </el-table-column>
        <el-table-column prop="source" label="来源" width="80" />
        <el-table-column label="操作" width="280">
          <template #default="{ row }">
            <el-button link size="small" type="primary" @click="runNow(row)">立即执行</el-button>
            <el-button link size="small" @click="togglePause(row)">{{ row.status === 'ACTIVE' ? '暂停' : '启动' }}</el-button>
            <el-button link size="small" @click="viewRuns(row)">历史</el-button>
            <el-button link size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="runDrawer" :title="currentReport?.name + ' · 执行历史'" size="50%">
      <el-table :data="runs" border size="small">
        <el-table-column prop="run_id" label="#" width="80" />
        <el-table-column prop="scheduled_at" label="计划时间" width="160" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="runStatusTag(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时(ms)" width="100" />
        <el-table-column prop="rows_returned" label="行数" width="80" />
        <el-table-column label="结果">
          <template #default="{ row }">
            <div v-if="row.result_summary">{{ row.result_summary }}</div>
            <div v-if="row.error_msg" style="color:#f56c6c;">⚠️ {{ row.error_code }}: {{ row.error_msg }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="biz_tokens_charged" label="Token" width="80" align="right" />
      </el-table>
    </el-drawer>
  </div>
</template>

<style scoped>
.page { padding: 16px 24px; }
</style>
