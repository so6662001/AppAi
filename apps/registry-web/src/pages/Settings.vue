<script setup lang="ts">
</script>

<template>
  <div class="page">
    <el-card>
      <template #header>设置</template>
      <el-form label-width="160px">
        <el-form-item label="默认新鲜度 SLA (分钟)"><el-input-number :model-value="60" /></el-form-item>
        <el-form-item label="默认可用性 SLA (%)"><el-input-number :model-value="99.5" :step="0.1" /></el-form-item>
        <el-form-item label="变更通知渠道">
          <el-checkbox-group>
            <el-checkbox value="EMAIL" checked>邮件</el-checkbox>
            <el-checkbox value="DINGTALK">钉钉</el-checkbox>
            <el-checkbox value="WECOM" checked>企业微信</el-checkbox>
            <el-checkbox value="INBOX" checked>站内信</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="Git 自动同步">
          <el-switch :model-value="true" />
          <span style="color:#909399;margin-left:8px;">注册中心改动自动 PR 到 metrics/*.yaml</span>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
