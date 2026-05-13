<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { changeApi } from '@/api/metrics';

const router = useRouter();
const list = ref<any[]>([]);
const filter = ref<any>({ status: '', mine: false, pending_my_approval: false });

async function fetchData() {
  try {
    list.value = await changeApi.list(filter.value);
  } catch {
    list.value = [
      { request_id: 128, metric_code: 'net_profit', change_type: 'FORMULA', from_version: '1.0.0', to_version: '2.0.0', status: 'SUBMITTED', created_by: 'zhang.san', created_at: '2026-05-13 09:15', impact_risk: 'HIGH' },
      { request_id: 127, metric_code: 'inv_turnover_days', change_type: 'SYNONYM', from_version: '1.0.0', to_version: '1.1.0', status: 'MERGED', created_by: 'li.si', created_at: '2026-05-12 16:20', impact_risk: 'LOW' },
      { request_id: 126, metric_code: 'customer_irr', change_type: 'CREATE', status: 'APPROVED', created_by: 'cfo', created_at: '2026-05-11 14:00', impact_risk: 'MEDIUM' },
    ];
  }
}
onMounted(fetchData);
</script>

<template>
  <div class="page">
    <el-card>
      <div class="toolbar">
        <el-select v-model="filter.status" placeholder="状态" clearable @change="fetchData" style="width:140px;">
          <el-option v-for="s in ['DRAFT','SUBMITTED','APPROVED','REJECTED','MERGED','CANCELED']"
                     :key="s" :label="s" :value="s" />
        </el-select>
        <el-checkbox v-model="filter.mine" @change="fetchData">我的申请</el-checkbox>
        <el-checkbox v-model="filter.pending_my_approval" @change="fetchData">待我审批</el-checkbox>
      </div>

      <el-table :data="list" border @row-click="(row: any) => router.push(`/requests/${row.request_id}`)">
        <el-table-column prop="request_id" label="#" width="80" />
        <el-table-column prop="metric_code" label="指标" width="200" />
        <el-table-column prop="change_type" label="变更类型" width="120">
          <template #default="{ row }"><el-tag>{{ row.change_type }}</el-tag></template>
        </el-table-column>
        <el-table-column label="版本">
          <template #default="{ row }">{{ row.from_version || '-' }} → {{ row.to_version || '-' }}</template>
        </el-table-column>
        <el-table-column prop="created_by" label="申请人" width="120" />
        <el-table-column prop="created_at" label="时间" width="160" />
        <el-table-column label="影响" width="100">
          <template #default="{ row }">
            <el-tag :type="row.impact_risk === 'HIGH' ? 'danger' : row.impact_risk === 'MEDIUM' ? 'warning' : 'info'">
              {{ row.impact_risk || '-' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.status === 'MERGED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
