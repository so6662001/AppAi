import { http, MetricSummary, MetricDetail } from './index';

export interface ListParams {
  q?: string;
  domain?: string;
  status?: string;
  sensitivity?: string;
  applicable?: string[];
  owner?: string;
  page?: number;
  size?: number;
  sort?: string;
}

export const metricsApi = {
  list: (params: ListParams = {}) =>
    http.get<{ total: number; page: number; size: number; items: MetricSummary[] }>(
      '/metrics', { params }
    ).then(r => r.data),

  get: (code: string, version?: string) =>
    http.get<MetricDetail>(`/metrics/${code}`, { params: { version } }).then(r => r.data),

  patch: (code: string, changes: Partial<MetricDetail>, change_note: string) =>
    http.patch(`/metrics/${code}`, { changes, change_note }).then(r => r.data),

  create: (data: Partial<MetricDetail>) =>
    http.post('/metrics', data).then(r => r.data),

  delete: (code: string) =>
    http.delete(`/metrics/${code}`).then(r => r.data),

  versions: (code: string) =>
    http.get(`/metrics/${code}/versions`).then(r => r.data),

  previewSql: (code: string, body: any) =>
    http.post(`/metrics/${code}/preview-sql`, body).then(r => r.data),

  sandboxRun: (code: string, body: any) =>
    http.post(`/metrics/${code}/sandbox-run`, body).then(r => r.data),

  lineage: (code: string, depth = 2, direction: 'up' | 'down' | 'both' = 'both') =>
    http.get(`/metrics/${code}/lineage`, { params: { depth, direction } }).then(r => r.data),

  impact: (code: string) =>
    http.get(`/metrics/${code}/impact`).then(r => r.data),
};

export const changeApi = {
  list: (filter: any = {}) =>
    http.get('/change-requests', { params: filter }).then(r => r.data),
  get: (id: number) => http.get(`/change-requests/${id}`).then(r => r.data),
  submit: (id: number) => http.post(`/change-requests/${id}/submit`).then(r => r.data),
  approve: (id: number, comment?: string) =>
    http.post(`/change-requests/${id}/approve`, { comment }).then(r => r.data),
  reject: (id: number, comment: string) =>
    http.post(`/change-requests/${id}/reject`, { comment }).then(r => r.data),
  merge: (id: number) => http.post(`/change-requests/${id}/merge`).then(r => r.data),
  cancel: (id: number) => http.post(`/change-requests/${id}/cancel`).then(r => r.data),
};

export const qualityApi = {
  events: (params: any = {}) => http.get('/quality/events', { params }).then(r => r.data),
  resolve: (id: number) => http.post(`/quality/events/${id}/resolve`).then(r => r.data),
  slaHeatmap: (params: any = {}) =>
    http.get('/quality/sla-heatmap', { params }).then(r => r.data),
};

export const overviewApi = {
  get: () => http.get('/overview').then(r => r.data),
};

export const subApi = {
  mine: () => http.get('/subscriptions').then(r => r.data),
  create: (data: any) => http.post('/subscriptions', data).then(r => r.data),
  cancel: (id: number) => http.delete(`/subscriptions/${id}`).then(r => r.data),
};
