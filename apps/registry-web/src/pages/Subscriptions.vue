<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { subApi } from '@/api/metrics';

const subs = ref<any[]>([]);
onMounted(async () => {
  try { subs.value = await subApi.mine(); } catch {
    subs.value = [
      { sub_id: 1, metric_code: 'M120', notify_on: ['FORMULA', 'DEPRECATE'], channel: ['INBOX', 'WECOM'] },
      { sub_id: 2, metric_code: 'M147', notify_on: ['SLA_BREACH'], channel: ['DINGTALK'] },
    ];
  }
});
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>我的订阅 ({{ subs.length }})</template>
      <el-table :data="subs" border>
        <el-table-column prop="metric_code" label="指标编号" />
        <el-table-column label="通知事件">
          <template #default="{ row }">
            <el-tag v-for="t in row.notify_on" :key="t" size="small" style="margin-right:4px;">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="渠道">
          <template #default="{ row }">
            <el-tag v-for="c in row.channel" :key="c" type="info" size="small" style="margin-right:4px;">{{ c }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default><el-button type="danger" link size="small">取消</el-button></template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
