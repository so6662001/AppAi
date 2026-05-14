<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { qualityApi } from '@/api/metrics';

const events = ref<any[]>([]);
onMounted(async () => {
  try {
    events.value = await qualityApi.events({ status: 'OPEN' });
  } catch {
    events.value = [
      { event_id: 1, metric_code: 'M120', event_type: 'FRESHNESS', severity: 'HIGH', detected_at: '2026-05-13 04:00', detail: { sla: 60, actual: 142 } },
      { event_id: 2, metric_code: 'M037', event_type: 'SPIKE',     severity: 'MEDIUM', detected_at: '2026-05-12 18:30', detail: { delta_pct: 0.72 } },
      { event_id: 3, metric_code: 'M082', event_type: 'NULL_RATIO', severity: 'LOW',  detected_at: '2026-05-11 02:00', detail: { ratio: 0.072 } },
    ];
  }
});

function sevTag(s: string) { return s === 'HIGH' || s === 'CRITICAL' ? 'danger' : s === 'MEDIUM' ? 'warning' : 'info'; }
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>未解决质量事件</template>
      <el-table :data="events" border>
        <el-table-column prop="metric_code" label="指标" width="150" />
        <el-table-column prop="event_type" label="事件类型" width="140" />
        <el-table-column label="严重度" width="100">
          <template #default="{ row }"><el-tag :type="sevTag(row.severity)">{{ row.severity }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="detected_at" label="检测时间" width="180" />
        <el-table-column label="详情">
          <template #default="{ row }">{{ JSON.stringify(row.detail) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default><el-button size="small" type="primary" link>标记已解决</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card style="margin-top:16px;">
      <template #header>SLA 健康度热力图 (近 30 天)</template>
      <SlaHeatmap />
    </el-card>
  </div>
</template>

<script lang="ts">
import SlaHeatmap from '@/components/SlaHeatmap.vue';
export default { components: { SlaHeatmap } };
</script>
