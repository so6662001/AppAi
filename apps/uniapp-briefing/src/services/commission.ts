/**
 * commission-service 客户端 - 提成查询/试算.
 */
const BASE = (import.meta as any).env?.VITE_API_BASE || 'https://api.steel-erp.com/v1';

function request<T>(path: string, opts: any = {}): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE + path,
      method: opts.method || 'GET',
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

export interface CommissionTemplateInfo {
  scheme_code: string;
  scheme_name: string;
  base_type: string;
  rate_default: number;
  rule_count: number;
}

export const commissionApi = {
  /** 列出 4 套内置模板. 网关路径 /v1/commission/templates → 服务路径 /v1/templates */
  listTemplates: () => request<Record<string, CommissionTemplateInfo>>('/commission/templates'),
  /** 拉某业务线模板 (含规则) */
  getTemplate: (bl: 'TRADE' | 'PROCESS' | 'MILL' | 'SHELL') =>
    request<{ scheme: any; rules: any[] }>(`/commission/templates/${bl}`),
  /** 直接套用模板试算 (orders 由调用方提供) */
  calcByTemplate: (params: {
    business_line: string; tenant_id: number; period_month: string;
    rep_id: number; rep_name: string; orders: any[];
  }) =>
    request<{ result: any }>(
      `/commission/calc/by-template?business_line=${params.business_line}` +
      `&tenant_id=${params.tenant_id}&period_month=${params.period_month}` +
      `&rep_id=${params.rep_id}&rep_name=${encodeURIComponent(params.rep_name)}`,
      { method: 'POST', data: params.orders }
    ),
};

/** 演示数据 fallback. */
export const demoTemplates: Record<string, CommissionTemplateInfo> = {
  TRADE:   { scheme_code: 'TPL_TRADE_GP30',    scheme_name: '【模板】钢贸-按挂牌毛利30%', base_type: 'LISTED_GROSS_PROFIT', rate_default: 0.30, rule_count: 4 },
  PROCESS: { scheme_code: 'TPL_PROCESS_FEE15', scheme_name: '【模板】加工-加工费15%+钢材毛利25%', base_type: 'PROCESSING_FEE', rate_default: 0.15, rule_count: 1 },
  MILL:    { scheme_code: 'TPL_MILL_TONNAGE',  scheme_name: '【模板】钢厂-按吨毛利元/吨', base_type: 'TON_GROSS_PROFIT', rate_default: 50.0, rule_count: 1 },
  SHELL:   { scheme_code: 'TPL_SHELL_SPREAD',  scheme_name: '【模板】皮包/纯撮合-按差价50%', base_type: 'SPREAD', rate_default: 0.50, rule_count: 2 },
};
