import type { ScheduledReport, ReportRun, ReportTemplate, ScheduledReportInput } from '@/types/scheduled-report';

const BASE = import.meta.env.VITE_API_BASE || 'https://api.steel-erp.com/v1';

function request<T>(path: string, opts: any = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + path,
      method: opts.method || 'GET',
      data: opts.data,
      header: {
        Authorization: `Bearer ${uni.getStorageSync('jwt') || ''}`,
        'Content-Type': 'application/json',
        ...(opts.header || {}),
      },
      success: (res: any) => {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data as T);
        else reject(res);
      },
      fail: reject,
    });
  });
}

export const scheduledReportApi = {
  list: (params: { status?: string; page?: number; size?: number } = {}) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<{ total: number; items: ScheduledReport[] }>(`/scheduled-reports?${qs}`);
  },
  get: (id: number) => request<ScheduledReport>(`/scheduled-reports/${id}`),
  create: (body: ScheduledReportInput) =>
    request<ScheduledReport>('/scheduled-reports', { method: 'POST', data: body }),
  update: (id: number, body: Partial<ScheduledReportInput>) =>
    request<ScheduledReport>(`/scheduled-reports/${id}`, { method: 'PATCH', data: body }),
  remove: (id: number) =>
    request(`/scheduled-reports/${id}`, { method: 'DELETE' }),
  pause: (id: number) =>
    request(`/scheduled-reports/${id}/pause`, { method: 'POST' }),
  resume: (id: number) =>
    request(`/scheduled-reports/${id}/resume`, { method: 'POST' }),
  runNow: (id: number) =>
    request<{ run_id: number }>(`/scheduled-reports/${id}/run-now`, { method: 'POST' }),
  runs: (id: number, limit = 30) =>
    request<ReportRun[]>(`/scheduled-reports/${id}/runs?limit=${limit}`),
  runDetail: (run_id: number) =>
    request<ReportRun & { sql_text?: string }>(`/scheduled-reports/runs/${run_id}`),
  resendRun: (run_id: number, body: any) =>
    request(`/scheduled-reports/runs/${run_id}/resend`, { method: 'POST', data: body }),
  templates: (params: { business_line?: string; role?: string; category?: string } = {}) => {
    const qs = new URLSearchParams(params as any).toString();
    return request<ReportTemplate[]>(`/scheduled-reports/templates?${qs}`);
  },
  subscribeTemplate: (tpl_id: number) =>
    request<ScheduledReport>(`/scheduled-reports/templates/${tpl_id}/subscribe`, { method: 'POST' }),
};

// 演示数据
export function fakeReports(): ScheduledReport[] {
  return [
    {
      report_id: 1, tenant_id: 1, user_id: 1,
      name: '老板日报-销售&库存', description: '每天 08:00 推送昨日核心',
      dsl_json: { metrics: ['sales_amount', 'inv_amount'], time: { preset: 'yesterday' } },
      schedule_type: 'cron', cron_expr: '0 0 8 * * ?', timezone: 'Asia/Shanghai',
      next_run_at: '2026-05-14 08:00', last_run_at: '2026-05-13 08:00',
      fail_count: 0, status: 'ACTIVE',
      channels: ['INAPP', 'WECOM'], source: 'template',
      created_at: '2026-05-01', updated_at: '2026-05-01',
    },
    {
      report_id: 2, tenant_id: 1, user_id: 1,
      name: '上周华东达交率', description: '我从聊天另存',
      dsl_json: {}, schedule_type: 'weekly', cron_expr: '0 0 9 ? * MON',
      timezone: 'Asia/Shanghai', next_run_at: '2026-05-19 09:00',
      status: 'ACTIVE', channels: ['INAPP'], source: 'chat',
      created_at: '2026-05-10', updated_at: '2026-05-10',
    },
    {
      report_id: 3, tenant_id: 1, user_id: 1,
      name: 'A 类 SKU 缺货预警', description: '',
      dsl_json: {}, schedule_type: 'daily', cron_expr: '0 0 7 * * ?',
      timezone: 'Asia/Shanghai', next_run_at: '2026-05-14 07:00',
      status: 'PAUSED', channels: ['INAPP', 'DINGTALK'], source: 'manual',
      created_at: '2026-05-03', updated_at: '2026-05-12',
    },
  ];
}

export function fakeTemplates(): ReportTemplate[] {
  return [
    { template_id: 1, business_line: 'TRADE', role: 'OWNER', category: 'DAILY',
      name: '老板日报-销售&库存', description: '每天 08:00 昨日核心指标',
      dsl_json: {}, cron_expr: '0 0 8 * * ?', channels: ['INAPP', 'WECOM'], popularity: 152 },
    { template_id: 2, business_line: 'TRADE', role: 'OWNER', category: 'DAILY',
      name: '资金占用 Top10', description: '每天 08:05 占款最高客户',
      dsl_json: {}, cron_expr: '0 5 8 * * ?', channels: ['INAPP', 'WECOM'], popularity: 98 },
    { template_id: 3, business_line: 'TRADE', role: 'OWNER', category: 'WEEKLY',
      name: '周报-毛利与挂价让利', description: '每周一 08:00 上周毛利结构',
      dsl_json: {}, cron_expr: '0 0 8 ? * MON', channels: ['INAPP', 'EMAIL'], popularity: 76 },
    { template_id: 4, business_line: 'PROCESS', role: 'MANAGER', category: 'DAILY',
      name: '加工厂日报-OEE&工单', description: '每天 07:30 昨日产线运行',
      dsl_json: {}, cron_expr: '0 30 7 * * ?', channels: ['INAPP', 'DINGTALK'], popularity: 64 },
    { template_id: 5, business_line: 'MILL', role: 'MANAGER', category: 'DAILY',
      name: '钢厂日报-产量&吨钢成本', description: '每天 07:00 昨日产量、成本',
      dsl_json: {}, cron_expr: '0 0 7 * * ?', channels: ['INAPP', 'WECOM'], popularity: 41 },
  ];
}
