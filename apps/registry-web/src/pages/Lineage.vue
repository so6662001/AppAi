<script setup lang="ts">
import { ref, onMounted } from 'vue';
import LineageGraph from '@/components/LineageGraph.vue';
import { metricsApi } from '@/api/metrics';

const code = ref('net_profit');
const nodes = ref<any[]>([]);
const edges = ref<any[]>([]);

async function load() {
  try {
    const r: any = await metricsApi.lineage(code.value);
    nodes.value = r.nodes || [];
    edges.value = r.edges || [];
  } catch {
    // 演示数据
    nodes.value = [
      { id: 'sales_amount', center: false }, { id: 'gross_profit', center: false },
      { id: 'other_income_amount', center: false }, { id: 'other_expense_amount', center: false },
      { id: 'contribution_margin' },
      { id: code.value, center: true }, { id: 'net_margin' }, { id: 'ton_net_profit' },
    ];
    edges.value = [
      { from: 'sales_amount', to: 'gross_profit' },
      { from: 'gross_profit', to: 'contribution_margin' },
      { from: 'other_income_amount', to: 'contribution_margin' },
      { from: 'other_expense_amount', to: 'contribution_margin' },
      { from: 'contribution_margin', to: code.value },
      { from: code.value, to: 'net_margin' },
      { from: code.value, to: 'ton_net_profit' },
    ];
  }
}
onMounted(load);
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        指标血缘
        <el-input v-model="code" placeholder="指标编号 / 名称" style="width:240px;margin-left:12px;" />
        <el-button type="primary" style="margin-left:4px;" @click="load">查询</el-button>
      </template>
      <LineageGraph :nodes="nodes" :edges="edges" height="600px" />
    </el-card>
  </div>
</template>
