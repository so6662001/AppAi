import axios from 'axios';

export const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/registry/v1',
  timeout: 15000,
});

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('jwt');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

http.interceptors.response.use(
  r => r,
  err => {
    const msg = err?.response?.data?.detail?.message || err?.response?.data?.message || err.message;
    // 使用 element-plus 时弹通知, 浏览器外用 console
    if (typeof (window as any).ElNotification === 'function') {
      (window as any).ElNotification({ type: 'error', message: msg });
    }
    return Promise.reject(err);
  }
);

export interface MetricSummary {
  metric_code: string;
  name: string;
  name_zh: string;
  domain: string;
  version: string;
  status: string;
  sensitivity: string;
  owner: string;
  sla_health?: string;
  call_count_7d?: number;
}

export interface MetricDetail extends MetricSummary {
  synonyms: string[];
  applicable: string[];
  fact: string;
  formula: string;
  semantics: string;
  time_agg: string;
  format: string;
  unit?: string;
  requires_metrics: string[];
  filter_expr?: string;
  join_tables: string[];
  bizToken_multiplier?: number;
  steward?: string;
  approvers?: string[];
  sla?: { freshness_minutes: number; availability: number; query_p95_ms: number };
  notes?: string;
  tags?: string[];
}
