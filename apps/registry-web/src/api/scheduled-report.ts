import axios from 'axios';

export const reportApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_REPORT || '/api/v1',
  timeout: 15000,
});
reportApi.interceptors.request.use((cfg) => {
  const t = localStorage.getItem('jwt');
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

export interface ScheduledReport {
  report_id: number;
  name: string;
  description?: string;
  status: 'ACTIVE' | 'PAUSED' | 'EXPIRED' | 'DELETED';
  schedule_type: string;
  cron_expr?: string;
  channels: string[];
  next_run_at?: string;
  last_run_at?: string;
  fail_count?: number;
  source: string;
  user_id: number;
  recipients?: string[];
  dsl_json?: any;
  created_at: string;
  updated_at: string;
}

export interface ReportRun {
  run_id: number;
  report_id: number;
  scheduled_at: string;
  finished_at?: string;
  duration_ms?: number;
  status: string;
  rows_returned?: number;
  result_summary?: string;
  error_code?: string;
  error_msg?: string;
  push_results?: any[];
  biz_tokens_charged?: number;
}

export const scheduledReportsApi = {
  list: (params: any = {}) =>
    reportApi.get<{ total: number; items: ScheduledReport[] }>('/scheduled-reports', { params }).then(r => r.data),
  get: (id: number) =>
    reportApi.get<ScheduledReport>(`/scheduled-reports/${id}`).then(r => r.data),
  create: (data: Partial<ScheduledReport>) =>
    reportApi.post<ScheduledReport>('/scheduled-reports', data).then(r => r.data),
  update: (id: number, data: Partial<ScheduledReport>) =>
    reportApi.patch<ScheduledReport>(`/scheduled-reports/${id}`, data).then(r => r.data),
  remove: (id: number) =>
    reportApi.delete(`/scheduled-reports/${id}`).then(r => r.data),
  pause: (id: number) => reportApi.post(`/scheduled-reports/${id}/pause`).then(r => r.data),
  resume: (id: number) => reportApi.post(`/scheduled-reports/${id}/resume`).then(r => r.data),
  runNow: (id: number) =>
    reportApi.post<{ run_id: number }>(`/scheduled-reports/${id}/run-now`).then(r => r.data),
  runs: (id: number, limit = 30) =>
    reportApi.get<ReportRun[]>(`/scheduled-reports/${id}/runs`, { params: { limit } }).then(r => r.data),
  runDetail: (run_id: number) =>
    reportApi.get(`/scheduled-reports/runs/${run_id}`).then(r => r.data),
  templates: (params: any = {}) =>
    reportApi.get('/scheduled-reports/templates', { params }).then(r => r.data),
};
