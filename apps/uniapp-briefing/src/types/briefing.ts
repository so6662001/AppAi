export type Severity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type CardType =
  | 'SUMMARY' | 'RISK' | 'ADVICE' | 'INSIGHT' | 'ABC'
  | 'FORECAST' | 'CAPITAL' | 'ANOMALY' | 'RECOMMEND' | 'BALANCE';

export interface CardAction {
  label: string;
  type: 'chat' | 'action' | 'navigate';
  dsl?: Record<string, any>;
  handler?: string;
  params?: Record<string, any>;
  path?: string;
  confirm?: { title: string; message: string };
}

export interface BriefingCard {
  card_id: number;
  type: CardType;
  severity: Severity;
  rank_score?: number;
  title: string;
  payload: any;
  source_metrics?: string[];
  actions: CardAction[];
  status?: string;
  expires_at?: string;
}

export interface BriefingFeed {
  biz_date: string;
  user: { id: number; role: string; business_line: 'TRADE' | 'PROCESS' | 'MILL' };
  cards: BriefingCard[];
}

export interface KpiSpec {
  metric: string;
  label: string;
  value: number;
  unit: string;
  format: 'amount' | 'ton' | 'percent' | 'price' | 'days' | 'count';
  trend?: { dir: 'up' | 'down' | 'flat'; delta_pct?: number; delta_abs?: number; baseline?: string };
  sparkline?: number[];
}
