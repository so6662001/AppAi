import type { BriefingFeed } from '@/types/briefing';

const BASE = import.meta.env.VITE_API_BASE || 'https://api.steel-erp.com/v1';

function request<T>(path: string, opts: UniApp.RequestOptions = {} as any): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + path,
      method: (opts.method as any) || 'GET',
      data: opts.data,
      header: {
        Authorization: `Bearer ${uni.getStorageSync('jwt') || ''}`,
        ...(opts.header || {}),
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data as T);
        else reject(res);
      },
      fail: reject,
    });
  });
}

export const briefingApi = {
  today: (date?: string) =>
    request<BriefingFeed>(`/briefing/today${date ? `?date=${date}` : ''}`),
  history: (from: string, to: string, page = 1, size = 30) =>
    request<{ items: BriefingFeed[]; total: number }>(
      `/briefing/history?from=${from}&to=${to}&page=${page}&size=${size}`
    ),
  markRead: (id: number) => request(`/briefing/cards/${id}/mark-read`, { method: 'POST' } as any),
  act: (id: number, body: any) => request(`/briefing/cards/${id}/act`, { method: 'POST', data: body } as any),
  ignore: (id: number) => request(`/briefing/cards/${id}/ignore`, { method: 'POST' } as any),
  feedback: (id: number, body: { vote: 'UP' | 'DOWN'; reason?: string; remark?: string }) =>
    request(`/briefing/cards/${id}/feedback`, { method: 'POST', data: body } as any),
  getLayout: () => request('/briefing/layout'),
  updateLayout: (body: any) => request('/briefing/layout', { method: 'PUT', data: body } as any),
};

// 演示数据 fallback (后端未起时使用)
export function fakeFeed(): BriefingFeed {
  return {
    biz_date: '2026-05-13',
    user: { id: 1, role: 'OWNER', business_line: 'TRADE' },
    cards: [
      {
        card_id: 1, type: 'SUMMARY', severity: 'LOW', rank_score: 100,
        title: '早安, 张总',
        payload: {
          greeting: '早安, 张总',
          date_label: '05-13 周三',
          kpis: [
            { metric: 'sales_amount', label: '昨日销售额', value: 18200000, unit: '元', format: 'amount',
              trend: { dir: 'up', delta_pct: 0.12, baseline: '比上周一' } },
            { metric: 'sales_tonnage', label: '昨日销售吨数', value: 4820, unit: '吨', format: 'ton',
              trend: { dir: 'down', delta_pct: -0.032 } },
            { metric: 'ton_gross_profit', label: '昨日吨毛利', value: 186, unit: '元/吨', format: 'price',
              trend: { dir: 'up', delta_abs: 22 } },
            { metric: 'inv_amount', label: '实时库存', value: 184500000, unit: '元', format: 'amount',
              trend: { dir: 'up', delta_pct: 0.014 } },
          ],
        },
        actions: [
          { label: '追问 AI', type: 'chat', dsl: { metrics: ['sales_amount'], time: { preset: 'yesterday' } } },
          { label: '看完整日报', type: 'navigate', path: '/pages/dashboard/daily' },
        ],
      },
      {
        card_id: 2, type: 'RISK', severity: 'HIGH', rank_score: 90,
        title: '客户【宝某科技】授信使用率 98.6%',
        payload: {
          entity_type: 'CUSTOMER', entity_name: '宝某科技',
          metrics: [
            { label: '授信额度', value: '¥1,000 万' },
            { label: '已用', value: '¥986 万' },
            { label: '逾期', value: '¥142 万', sub: 'HIGH' },
          ],
          risk_score: 0.81,
          ai_advice: [
            '暂停新订单发货',
            '限期 7 天内回款 200 万以上',
            '联系客户经理 王某',
          ],
        },
        actions: [
          { label: '一键暂停', type: 'action', handler: 'freezeShipment', params: { customer_id: 12345 },
            confirm: { title: '确认暂停', message: '将冻结该客户所有新订单发货, 是否继续?' } },
          { label: '指派客户经理', type: 'action', handler: 'assignManager' },
          { label: '查看详情', type: 'navigate', path: '/pages/customer/detail?id=12345' },
          { label: '追问 AI', type: 'chat', dsl: { metrics: ['customer_risk_score', 'ar_outstanding'], filters: [{ field: 'customer.customer_id', op: '=', value: 12345 }] } },
        ],
      },
      {
        card_id: 3, type: 'ADVICE', severity: 'HIGH', rank_score: 80,
        title: '建议: 加快出货',
        payload: {
          context: '沙钢 Q355B 热卷',
          reason: '当前库存 1,820 吨 (高于均值 23%), 指数预计下周下行 -1.8%',
          suggested_actions: [
            { label: '挂特价', detail: '建议挂 4,150 元/吨, 主动联系 Top10 客户' },
            { label: '套保对冲', detail: '建议在 HC 合约空 500 吨' },
          ],
        },
        actions: [
          { label: '生成特价单', type: 'action', handler: 'createDiscountSku' },
          { label: '推送给业务员', type: 'action', handler: 'pushToSales' },
          { label: '追问 AI', type: 'chat' },
        ],
      },
      {
        card_id: 4, type: 'CAPITAL', severity: 'MEDIUM', rank_score: 70,
        title: '客户资金占用 Top5',
        payload: {
          rows: [
            { rank: 1, name: '客户A', capital: 21800000, irr: 0.182, label: '👍' },
            { rank: 2, name: '客户B', capital: 16500000, irr: 0.064, label: '⚠️' },
            { rank: 3, name: '客户C', capital: 14200000, irr: 0.091, label: '' },
            { rank: 4, name: '客户D', capital: 12800000, irr: 0.032, label: '❗' },
            { rank: 5, name: '客户E', capital:  9800000, irr: -0.014, label: '🚨' },
          ],
        },
        actions: [
          { label: '全部客户', type: 'navigate', path: '/pages/capital/customers' },
          { label: '追问 AI', type: 'chat' },
        ],
      },
      {
        card_id: 5, type: 'FORECAST', severity: 'MEDIUM', rank_score: 60,
        title: '下周预测',
        payload: {
          metric: '螺纹钢吨毛利',
          current: 186, forecast: 142,
          lower: 128, upper: 158,
          mape: 0.082, confidence: 'high',
        },
        actions: [
          { label: '看预测曲线', type: 'navigate', path: '/pages/forecast/ton-gp' },
          { label: '追问归因', type: 'chat' },
        ],
      },
      {
        card_id: 6, type: 'BALANCE', severity: 'MEDIUM', rank_score: 50,
        title: 'Token 余额提醒',
        payload: {
          current: 12800, total: 5000000, used_pct: 0.997,
          eta: '今日内用完',
        },
        actions: [
          { label: '立即续费', type: 'navigate', path: '/pages/ai/plan-shop' },
          { label: '查看用量', type: 'navigate', path: '/pages/ai/usage' },
        ],
      },
    ],
  };
}
