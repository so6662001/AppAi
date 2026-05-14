<script setup lang="ts">
/**
 * 多端兼容图表组件
 * - H5/App: ECharts (动态 import 减少首屏体积)
 * - 小程序: uCharts (经条件编译切换, 这里给 ECharts 路径; 小程序构建时替换)
 *
 * props:
 *   chart:  line | bar | pie | heatmap
 *   x:      x 轴字段名
 *   series: [{name, field}]
 *   rows:   [{[field]: value}]
 */
import { ref, onMounted, watch, nextTick } from 'vue';

interface Series { name: string; field: string }
const props = defineProps<{
  chart: 'line' | 'bar' | 'pie' | 'heatmap';
  x?: string;
  series: Series[];
  rows: Record<string, any>[];
  height?: number;
}>();

const chartRef = ref<HTMLElement | null>(null);
let instance: any = null;
let echarts: any = null;

async function ensureLib() {
  if (echarts) return;
  try {
    echarts = await import('echarts/core');
    const { LineChart, BarChart, PieChart, HeatmapChart } = await import('echarts/charts');
    const { GridComponent, TooltipComponent, LegendComponent, VisualMapComponent } = await import('echarts/components');
    const { CanvasRenderer } = await import('echarts/renderers');
    echarts.use([LineChart, BarChart, PieChart, HeatmapChart, GridComponent,
                 TooltipComponent, LegendComponent, VisualMapComponent, CanvasRenderer]);
  } catch {
    echarts = null;
  }
}

function buildOption() {
  const { chart, x, series, rows } = props;
  if (chart === 'pie') {
    return {
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: '60%',
        data: rows.map(r => ({ name: String(r[x || 'name']), value: r[series[0].field] }))
      }]
    };
  }
  if (chart === 'heatmap') {
    const xs = Array.from(new Set(rows.map(r => r.x)));
    const ys = Array.from(new Set(rows.map(r => r.y)));
    return {
      tooltip: {},
      grid: { height: '70%' },
      xAxis: { type: 'category', data: xs },
      yAxis: { type: 'category', data: ys },
      visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', bottom: 0 },
      series: [{ type: 'heatmap', data: rows.map(r => [r.x, r.y, r.value]) }]
    };
  }
  return {
    tooltip: { trigger: 'axis' },
    legend: { data: series.map(s => s.name) },
    grid: { left: 40, right: 20, top: 30, bottom: 30 },
    xAxis: { type: 'category', data: rows.map(r => r[x || 'biz_date']) },
    yAxis: { type: 'value' },
    series: series.map(s => ({
      name: s.name, type: chart,
      data: rows.map(r => r[s.field]),
      smooth: chart === 'line',
    }))
  };
}

async function render() {
  await ensureLib();
  await nextTick();
  if (!chartRef.value || !echarts) return;
  if (!instance) instance = echarts.init(chartRef.value);
  instance.setOption(buildOption());
}

onMounted(render);
watch(() => [props.chart, props.rows, props.series], render, { deep: true });
</script>

<template>
  <view class="chart-wrap" :style="{ height: (height || 240) + 'rpx' }">
    <!-- H5/App 用 div + ECharts canvas -->
    <div ref="chartRef" class="chart-canvas" />
  </view>
</template>

<style scoped>
.chart-wrap { width: 100%; min-height: 200px; }
.chart-canvas { width: 100%; height: 100%; }
</style>
