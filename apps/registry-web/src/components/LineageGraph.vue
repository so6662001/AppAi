<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import * as echarts from 'echarts/core';
import { GraphChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer]);

const props = defineProps<{
  nodes: Array<{ id: string; type?: string; center?: boolean; name?: string }>;
  edges: Array<{ from: string; to: string }>;
  height?: string;
}>();

const el = ref<HTMLElement | null>(null);
let chart: echarts.ECharts | null = null;

function render() {
  if (!el.value) return;
  if (!chart) chart = echarts.init(el.value);
  const nodes = (props.nodes || []).map(n => ({
    id: n.id,
    name: n.name || n.id,
    symbolSize: n.center ? 50 : 30,
    itemStyle: { color: n.center ? '#1989fa' : '#67c23a' },
    label: { show: true },
  }));
  const links = (props.edges || []).map(e => ({ source: e.from, target: e.to }));
  chart.setOption({
    tooltip: { formatter: (p: any) => p.dataType === 'node' ? p.data.name : `${p.data.source} → ${p.data.target}` },
    legend: [{ data: ['指标'] }],
    series: [{
      type: 'graph', layout: 'force',
      roam: true, draggable: true,
      data: nodes, links,
      categories: [{ name: '指标' }],
      lineStyle: { color: '#909399', curveness: 0.2 },
      label: { position: 'right' },
      force: { repulsion: 200, edgeLength: 100 },
    }]
  });
}

onMounted(() => nextTick(render));
watch(() => [props.nodes, props.edges], () => nextTick(render), { deep: true });
</script>

<template>
  <div ref="el" :style="{ height: height || '500px', width: '100%' }" />
</template>
