export type ReportStatus = 'ACTIVE' | 'PAUSED' | 'EXPIRED' | 'DELETED';
export type ScheduleType = 'cron' | 'interval' | 'daily' | 'weekly' | 'monthly' | 'once';
export type PushChannel = 'INAPP' | 'WECOM' | 'DINGTALK' | 'EMAIL' | 'UNI_PUSH' | 'SMS';

export interface ScheduledReport {
  report_id: number;
  tenant_id: number;
  user_id: number;
  name: string;
  description?: string;
  dsl_json: Record<string, any>;
  question?: string;
  render_blocks?: string[];
  chart_spec?: Record<string, any>;
  schedule_type: ScheduleType;
  cron_expr?: string;
  timezone?: string;
  next_run_at?: string;
  last_run_at?: string;
  fail_count?: number;
  status: ReportStatus;
  recipients?: string[];
  channels: PushChannel[];
  push_silent_if_empty?: boolean;
  push_format?: 'card' | 'table' | 'image' | 'excel';
  effective_from?: string;
  effective_to?: string;
  max_run_count?: number;
  created_at: string;
  updated_at: string;
  source?: 'chat' | 'manual' | 'template';
}

export interface ReportRun {
  run_id: number;
  report_id: number;
  scheduled_at: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'EMPTY' | 'CANCELED';
  error_code?: string;
  error_msg?: string;
  rows_returned?: number;
  blocks_json?: any[];
  result_summary?: string;
  push_results?: Array<{ channel: string; status: string; latency_ms: number; error?: string }>;
  biz_tokens_charged?: number;
}

export interface ReportTemplate {
  template_id: number;
  business_line?: string;
  role?: string;
  category?: string;
  name: string;
  description?: string;
  dsl_json: Record<string, any>;
  cron_expr: string;
  channels: PushChannel[];
  popularity?: number;
}

export interface ScheduledReportInput {
  name: string;
  description?: string;
  dsl_json: Record<string, any>;
  question?: string;
  render_blocks?: string[];
  schedule_type: ScheduleType;
  cron_expr?: string;
  timezone?: string;
  recipients?: string[];
  channels: PushChannel[];
  push_silent_if_empty?: boolean;
  push_format?: string;
  effective_to?: string;
  max_run_count?: number;
  source?: string;
}
