/** Onboarding API */
const BASE = import.meta.env.VITE_REGISTRY_API || 'https://api.steel-erp.com/api/registry/v1';

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

export const onboardingApi = {
  getPreferences: () => request<any>('/user/preferences'),
  savePreferences: (body: any) => request('/user/preferences', { method: 'PUT', data: body }),
  recommendPack: (biz: string, role: string) =>
    request<any>(`/metric-packs/recommend?biz=${biz}&role=${role}`),
  visibleMetrics: () => request<any>('/user/visible-metrics'),
};

export const BUSINESS_LINES = [
  { code: 'TRADE',   name: '钢铁贸易',   icon: '📦', desc: '买进卖出, 现货 + 期货套保' },
  { code: 'PROCESS', name: '钢材加工',   icon: '🔧', desc: '剪切 / 开平 / 纵剪 / 酸洗' },
  { code: 'MILL',    name: '钢材生产厂', icon: '🏭', desc: '炼钢 / 轧钢 / 镀锌' },
];

export const ROLES_BY_BIZ: Record<string, { code: string; name: string; emoji: string }[]> = {
  TRADE: [
    { code: 'OWNER',            name: '老板/总经理', emoji: '👨‍💼' },
    { code: 'SALES_DIRECTOR',   name: '销售总监',   emoji: '📊' },
    { code: 'SALES_REP',        name: '业务员',     emoji: '💰' },
    { code: 'CFO',              name: '财务总监',   emoji: '📈' },
    { code: 'FINANCE_STAFF',    name: '财务专员',   emoji: '🧾' },
    { code: 'RISK_MANAGER',     name: '风控经理',   emoji: '🛡️' },
    { code: 'HEDGE_TRADER',     name: '套保员',     emoji: '📉' },
    { code: 'PROCUREMENT_DIR',  name: '采购总监',   emoji: '📋' },
    { code: 'WH_MANAGER',       name: '仓库经理',   emoji: '📦' },
    { code: 'WH_STAFF',         name: '仓管员',     emoji: '🔧' },
    { code: 'CUSTOMER_SERVICE', name: '客服',       emoji: '☎️' },
  ],
  PROCESS: [
    { code: 'PROCESS_OWNER',   name: '加工厂厂长', emoji: '👨‍💼' },
    { code: 'PRODUCTION_MGR',  name: '生产经理',   emoji: '⚙️' },
    { code: 'QUALITY_MGR',     name: '质量经理',   emoji: '✅' },
    { code: 'EQUIPMENT_MGR',   name: '设备经理',   emoji: '🛠️' },
    { code: 'PLAN_MGR',        name: '计划经理',   emoji: '📅' },
    { code: 'OPERATOR',        name: '操作工',     emoji: '👷' },
  ],
  MILL: [
    { code: 'MILL_OWNER',       name: '钢厂厂长',     emoji: '👨‍💼' },
    { code: 'MILL_VP',          name: '生产副总',     emoji: '🏭' },
    { code: 'CFO',              name: 'CFO',          emoji: '📈' },
    { code: 'STEELMAKING_HEAD', name: '炼钢车间主任', emoji: '🔥' },
    { code: 'ROLLING_HEAD',     name: '轧钢车间主任', emoji: '🔩' },
    { code: 'COATING_HEAD',     name: '镀锌车间主任', emoji: '🪙' },
    { code: 'QC_DIRECTOR',      name: '质检主管',     emoji: '🔬' },
    { code: 'ENERGY_MGR',       name: '能源经理',     emoji: '⚡' },
  ],
};

export const INTERESTS_BY_ROLE: Record<string, string[]> = {
  // 默认推荐勾选 (其余可手动勾)
  OWNER:           ['销售业绩', '客户管理', '应收账款', '库存周转', '净利率', '风险敞口'],
  SALES_DIRECTOR:  ['销售业绩', '客户管理', '吨毛利', '挂价让利'],
  SALES_REP:       ['销售业绩', '客户管理', '应收账款'],
  CFO:             ['净利率', '应收账款', '资金占用', '风险敞口'],
  FINANCE_STAFF:   ['应收账款', '应付账款'],
  RISK_MANAGER:    ['风险敞口', '套保头寸'],
  HEDGE_TRADER:    ['套保头寸', '库存浮亏'],
  PROCUREMENT_DIR: ['采购成本', '供应商达交'],
  WH_MANAGER:      ['库存周转', '库龄'],
  WH_STAFF:        ['收发货'],
  CUSTOMER_SERVICE:['客诉', '退货'],

  PROCESS_OWNER:   ['产量', '设备OEE', '良率', '吨钢成本'],
  PRODUCTION_MGR:  ['产量', '设备OEE', '工单进度'],
  QUALITY_MGR:     ['质量缺陷', 'PPM', '客诉'],
  EQUIPMENT_MGR:   ['设备OEE', 'MTBF/MTTR'],

  MILL_OWNER:      ['产量', '吨钢成本', '净利率', '能耗'],
  MILL_VP:         ['产量', '设备OEE', '良率', '能耗'],
};

export const ALL_INTERESTS = [
  '销售业绩', '客户管理', '应收账款', '吨毛利', '挂价让利',
  '库存周转', '库龄', '采购成本', '供应商达交', '应付账款',
  '资金占用', '净利率', '风险敞口', '套保头寸', '库存浮亏',
  '收发货', '客诉', '退货',
  '产量', '设备OEE', '良率', '工单进度', '质量缺陷', 'PPM',
  'MTBF/MTTR', '吨钢成本', '能耗',
];
