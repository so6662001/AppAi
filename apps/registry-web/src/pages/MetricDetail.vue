<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { metricsApi } from '@/api/metrics';
import type { MetricDetail } from '@/api/index';

const props = defineProps<{ code: string }>();
const router = useRouter();
const data = ref<MetricDetail | null>(null);
const activeTab = ref('definition');
const previewSql = ref<string>('-- 点击"试编译"生成 SQL');
const previewLoading = ref(false);

onMounted(async () => {
  try {
    data.value = await metricsApi.get(props.code);
  } catch {
    // 演示
    data.value = {
      metric_code: 'M120', name: 'net_profit', name_zh: '销售净利润',
      domain: 'SALES', version: '2.0.0', status: 'PUBLISHED',
      sensitivity: 'HIGH', owner: 'CFO', synonyms: ['净利', '净利润', '净赚'],
      applicable: ['TRADE', 'PROCESS', 'MILL'],
      fact: 'dws_sales_daily', formula: 'contribution_margin - allocated_period_expense',
      semantics: 'additive', time_agg: 'sum', format: 'amount',
      requires_metrics: ['contribution_margin'],
      join_tables: ['dws_period_expense_monthly'],
      bizToken_multiplier: 1.5,
      steward: 'data-team',
      approvers: ['cfo@steel-erp.com'],
      sla: { freshness_minutes: 60, availability: 99.5, query_p95_ms: 2000 },
      notes: '= 贡献毛利 - 期间费用分摊; 日粒度按比例摊, 月以上可信',
      tags: ['财务', '经营关键'],
    } as MetricDetail;
  }
});

async function runPreview() {
  if (!data.value) return;
  previewLoading.value = true;
  try {
    const r = await metricsApi.previewSql(data.value.metric_code, {
      dimensions: ['org.region'], time: { preset: 'last_month', grain: 'month' }, filters: [],
    });
    previewSql.value = r.sql;
  } catch {
    previewSql.value = `-- 演示 (后端未起)
WITH base AS (
  SELECT date_trunc('month', biz_date) AS biz_month, region,
         SUM(gross_profit + other_income_amount - other_expense_amount) AS contribution_margin
  FROM dws_sales_daily JOIN dim_org USING(org_id)
  WHERE tenant_id = :p1
    AND biz_date BETWEEN :p2 AND :p3
  GROUP BY 1, 2
),
exp AS (
  SELECT biz_month, region, SUM(amount) AS period_exp
  FROM dws_period_expense_monthly JOIN dim_org USING(org_id)
  WHERE tenant_id = :p1 AND biz_month BETWEEN :p4 AND :p5
  GROUP BY 1, 2
)
SELECT b.biz_month, b.region,
       b.contribution_margin - e.period_exp AS net_profit
FROM base b LEFT JOIN exp e USING(biz_month, region)
ORDER BY net_profit DESC
LIMIT 1000;`;
  } finally {
    previewLoading.value = false;
  }
}
</script>

<template>
  <div class="page" v-if="data">
    <el-page-header @back="router.back()" style="margin-bottom:12px;">
      <template #content>
        <span class="metric-label" style="font-size:18px;">{{ data.name_zh }} ({{ data.metric_code }})</span>
        <el-tag size="small" type="info" style="margin-left:8px;">v{{ data.version }}</el-tag>
        <el-tag size="small" type="success" style="margin-left:4px;">{{ data.status }}</el-tag>
        <el-tag size="small" :type="data.sensitivity === 'HIGH' ? 'danger' : 'warning'" style="margin-left:4px;">
          敏感度: {{ data.sensitivity }}
        </el-tag>
      </template>
      <template #extra>
        <el-button>订阅</el-button>
        <el-button type="primary" @click="router.push(`/metrics/${data.metric_code}/edit`)">编辑</el-button>
        <el-button type="danger" plain>废弃</el-button>
      </template>
    </el-page-header>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="口径" name="definition">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="名称">{{ data.name }}</el-descriptions-item>
          <el-descriptions-item label="域">{{ data.domain }}</el-descriptions-item>
          <el-descriptions-item label="同义词">
            <div class="tag-row">
              <el-tag v-for="s in data.synonyms" :key="s" size="small">{{ s }}</el-tag>
            </div>
          </el-descriptions-item>
          <el-descriptions-item label="适用类型">
            <el-tag v-for="a in data.applicable" :key="a" size="small" type="primary" effect="plain">{{ a }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="主表">{{ data.fact }}</el-descriptions-item>
          <el-descriptions-item label="Join">{{ data.join_tables?.join(', ') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="公式" :span="2">
            <pre class="sql-preview" style="white-space:pre-wrap;">{{ data.formula }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="依赖指标" :span="2">
            <el-tag v-for="r in data.requires_metrics" :key="r" size="small" type="info"
                    style="margin-right:4px;cursor:pointer;" @click="router.push(`/metrics/${r}`)">
              {{ r }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="语义">{{ data.semantics }}</el-descriptions-item>
          <el-descriptions-item label="跨日聚合">{{ data.time_agg }}</el-descriptions-item>
          <el-descriptions-item label="格式">{{ data.format }} {{ data.unit ? `(${data.unit})` : '' }}</el-descriptions-item>
          <el-descriptions-item label="计费乘数">{{ data.bizToken_multiplier || 1 }}x</el-descriptions-item>
          <el-descriptions-item label="Owner">{{ data.owner }}</el-descriptions-item>
          <el-descriptions-item label="Steward">{{ data.steward || '-' }}</el-descriptions-item>
          <el-descriptions-item label="审批人">{{ data.approvers?.join(', ') || '-' }}</el-descriptions-item>
          <el-descriptions-item label="SLA">
            新鲜度&lt;{{ data.sla?.freshness_minutes }}min · 可用性 {{ data.sla?.availability }}% · P95&lt;{{ data.sla?.query_p95_ms }}ms
          </el-descriptions-item>
          <el-descriptions-item label="标签">
            <el-tag v-for="t in data.tags" :key="t" size="small">{{ t }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注" :span="2">{{ data.notes || '-' }}</el-descriptions-item>
        </el-descriptions>
      </el-tab-pane>

      <el-tab-pane label="SQL 预览" name="sql">
        <el-card>
          <template #header>
            <el-button type="primary" @click="runPreview" :loading="previewLoading">试编译</el-button>
            <span style="margin-left:8px;color:#909399;font-size:12px;">示例参数: time=last_month, dim=org.region</span>
          </template>
          <pre class="sql-preview">{{ previewSql }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="历史版本" name="history">
        <el-empty description="待接入版本历史接口" />
      </el-tab-pane>

      <el-tab-pane label="质量监控" name="quality">
        <el-empty description="待接入数据质量趋势图" />
      </el-tab-pane>

      <el-tab-pane label="下游 / 影响" name="impact">
        <el-alert type="info" :closable="false" style="margin-bottom:8px;"
          title="变更前必跑影响分析" description="自动列出下游指标、看板、近 7 天 AI 会话、计费规则、订阅者列表" />
        <el-empty description="待接入影响分析接口" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>
