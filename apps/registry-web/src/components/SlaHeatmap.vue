<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue';
import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import { TooltipComponent, VisualMapComponent, GridComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import { qualityApi } from '@/api/metrics';

echarts.use([HeatmapChart, TooltipComponent, VisualMapComponent, GridComponent, CanvasRenderer]);

const el = ref<HTMLElement | null>(null);
const props = defineProps<{ days?: number }>();

async function render() {
  if (!el.value) return;
  const chart = echarts.init(el.value);

  let matrix: any[] = [];
  let metrics: string[] = [];
  let dates: string[] = [];

  try {
    const r: any = await qualityApi.slaHeatmap({ days: props.days || 30 });
    matrix = r.matrix || [];
    metrics = Array.from(new Set(matrix.map(c => c.metric_code)));
    dates = Array.from(new Set(matrix.map(c => c.date)));
  } catch {
    metrics = ['M001', 'M006', 'M120', 'M131', 'M139'];
    dates = Array.from({ length: 30 }, (_, i) => {
      const d = new Date(); d.setDate(d.getDate() - (29 - i));
      return d.toISOString().slice(0, 10);
    });
    matrix = metrics.flatMap(m => dates.map(d => ({
      metric_code: m, date: d, sla_pct: Math.random() * 100,
    })));
  }

  const data = matrix.map(c => [
    dates.indexOf(c.date), metrics.indexOf(c.metric_code),
    Math.round(c.sla_pct * 10) / 10,
  ]);

  chart.setOption({
    tooltip: { position: 'top',
               formatter: (p: any) => `${metrics[p.data[1]]} / ${dates[p.data[0]]}: ${p.data[2]}%` },
    grid: { height: '70%', top: '10%' },
    xAxis: { type: 'category', data: dates, splitArea: { show: true } },
    yAxis: { type: 'category', data: metrics, splitArea: { show: true } },
    visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal',
                 left: 'center', bottom: '5%',
                 inRange: { color: ['#f56c6c', '#e6a23c', '#67c23a'] } },
    series: [{ name: 'SLA', type: 'heatmap', data,
               label: { show: false } }],
  });
}

onMounted(() => nextTick(render));
</script>

<template>
  <div ref="el" style="height: 480px; width: 100%;" />
</template>
