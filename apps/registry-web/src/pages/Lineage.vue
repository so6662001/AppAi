<script setup lang="ts">
import { ref } from 'vue';
const code = ref('net_profit');
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>
        指标血缘
        <el-input v-model="code" placeholder="指标编号 / 名称" style="width:240px;margin-left:12px;" />
        <el-button type="primary" style="margin-left:4px;">查询</el-button>
      </template>
      <el-empty description="待接入 ECharts/G6 渲染 nodes + edges 图谱" />
      <pre class="sql-preview" style="background:#fafafa;color:#333;">
示例血缘 (基于 metric_def.requires_metrics + metric_usage_ref):

    sales_amount (M001) ─┐
    gross_profit (M006) ─┼─► contribution_margin (M119) ─► net_profit (M120) ★
    other_income (M107) ─┘                                       │
    other_expense (M113) ─                                       ├─► net_margin (M121)
                                                                 └─► ton_net_profit (M122)
      </pre>
    </el-card>
  </div>
</template>
