<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { overviewApi } from '@/api/metrics';

const router = useRouter();
const data = ref<any>({
  total_metrics: 0,
  by_status: {},
  owner_top5: [],
  sla_health: { healthy: 0, at_risk: 0, failing: 0 },
  top_called_7d: [],
  recent_changes: [],
});

onMounted(async () => {
  try {
    data.value = await overviewApi.get();
  } catch {
    // 演示数据(后端未起时)
    data.value = {
      total_metrics: 178,
      by_status: { PUBLISHED: 168, DRAFT: 8, DEPRECATED: 2 },
      owner_top5: [
        { owner: '张三', count: 42 }, { owner: '李四', count: 31 },
        { owner: '王五', count: 27 }, { owner: '赵六', count: 20 },
        { owner: '钱七', count: 18 },
      ],
      sla_health: { healthy: 162, at_risk: 11, failing: 5 },
      top_called_7d: [
        { metric_code: 'M001', name: 'sales_amount', calls: 12340, cost_cny: 32.1 },
        { metric_code: 'M006', name: 'gross_profit', calls: 8920,  cost_cny: 24.6 },
        { metric_code: 'M018', name: 'on_time_delivery_rate', calls: 6420, cost_cny: 11.8 },
        { metric_code: 'M120', name: 'net_profit', calls: 1180,  cost_cny: 28.4 },
      ],
      recent_changes: [
        { request_id: 128, metric_code: 'net_profit', change_type: 'FORMULA', created_by: 'zhang.san', status: 'SUBMITTED' },
        { request_id: 127, metric_code: 'inv_turnover_days', change_type: 'SYNONYM', created_by: 'li.si', status: 'MERGED' },
      ],
    };
  }
});

function goRequest(id: number) { router.push(`/requests/${id}`); }
</script>

<template>
  <div class="page">
    <el-row :gutter="16">
      <el-col :span="8">
        <el-card class="kpi-card">
          <div class="section-title">指标总数</div>
          <div class="num">{{ data.total_metrics }}</div>
          <el-divider />
          <el-space wrap>
            <el-tag type="success">PUBLISHED {{ data.by_status?.PUBLISHED || 0 }}</el-tag>
            <el-tag type="warning">DRAFT {{ data.by_status?.DRAFT || 0 }}</el-tag>
            <el-tag type="info">DEPRECATED {{ data.by_status?.DEPRECATED || 0 }}</el-tag>
          </el-space>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="kpi-card">
          <div class="section-title">Owner Top 5</div>
          <el-table :data="data.owner_top5" :show-header="false" size="small">
            <el-table-column prop="owner" />
            <el-table-column prop="count" align="right" width="80" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card class="kpi-card">
          <div class="section-title">SLA 健康</div>
          <el-row :gutter="8">
            <el-col :span="8">
              <div class="num" style="color:#67c23a;">{{ data.sla_health?.healthy }}</div>
              <div class="label">健康</div>
            </el-col>
            <el-col :span="8">
              <div class="num" style="color:#e6a23c;">{{ data.sla_health?.at_risk }}</div>
              <div class="label">风险</div>
            </el-col>
            <el-col :span="8">
              <div class="num" style="color:#f56c6c;">{{ data.sla_health?.failing }}</div>
              <div class="label">失败</div>
            </el-col>
          </el-row>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16" style="margin-top:16px;">
      <el-col :span="12">
        <el-card>
          <template #header>近 7 天 Top 调用指标</template>
          <el-table :data="data.top_called_7d" size="small" border>
            <el-table-column prop="metric_code" label="编号" width="100" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="calls" label="调用次数" align="right" />
            <el-table-column prop="cost_cny" label="成本(¥)" align="right" />
          </el-table>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>最近变更</template>
          <el-table :data="data.recent_changes" size="small" border @row-click="(row: any) => goRequest(row.request_id)">
            <el-table-column prop="request_id" label="#" width="80" />
            <el-table-column prop="metric_code" label="指标" />
            <el-table-column prop="change_type" label="类型" />
            <el-table-column prop="created_by" label="申请人" />
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="row.status === 'MERGED' ? 'success' : 'warning'">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
