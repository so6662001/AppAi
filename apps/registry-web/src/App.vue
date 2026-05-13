<script setup lang="ts">
import { useRoute } from 'vue-router';
import { Document, DataAnalysis, List as IList, EditPen, Histogram, Connection, Setting } from '@element-plus/icons-vue';

const route = useRoute();
</script>

<template>
  <el-container style="height:100%;">
    <el-aside width="220px" style="background:#001529;color:#fff;">
      <div style="padding:18px;font-weight:600;font-size:16px;color:#fff;">
        指标注册中心
      </div>
      <el-menu :default-active="route.path" router background-color="#001529" text-color="#bfbfbf"
               active-text-color="#fff" style="border:none;">
        <el-menu-item index="/"><el-icon><Document /></el-icon><span>首页</span></el-menu-item>
        <el-menu-item index="/metrics"><el-icon><IList /></el-icon><span>指标列表</span></el-menu-item>
        <el-menu-item index="/requests"><el-icon><EditPen /></el-icon><span>变更申请</span></el-menu-item>
        <el-menu-item index="/scheduled-reports"><el-icon><DataAnalysis /></el-icon><span>定时报表</span></el-menu-item>
        <el-menu-item index="/quality"><el-icon><DataAnalysis /></el-icon><span>数据质量</span></el-menu-item>
        <el-menu-item index="/lineage"><el-icon><Connection /></el-icon><span>血缘图谱</span></el-menu-item>
        <el-menu-item index="/subscriptions"><el-icon><Histogram /></el-icon><span>我的订阅</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>设置</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="padding:0;background:#f5f7fa;">
      <router-view />
    </el-main>
  </el-container>
</template>
