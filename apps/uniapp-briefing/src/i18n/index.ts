/**
 * 简化 i18n: 默认中文, 英文用于海外钢厂. 实际生产建议接 vue-i18n.
 */
type Locale = 'zh-CN' | 'en';

const ZH: Record<string, string> = {
  'briefing.title': '经营早报',
  'briefing.history': '历史早报',
  'briefing.settings': '早报设置',
  'card.summary': '摘要',
  'card.risk': '风险预警',
  'card.advice': '建议',
  'card.forecast': '预测',
  'action.askAi': '追问 AI',
  'action.detail': '查看详情',
  'action.export': '导出',
  'severity.LOW': '低',
  'severity.MEDIUM': '中',
  'severity.HIGH': '高',
  'severity.CRITICAL': '严重',
};

const EN: Record<string, string> = {
  'briefing.title': 'Daily Briefing',
  'briefing.history': 'History',
  'briefing.settings': 'Settings',
  'card.summary': 'Summary',
  'card.risk': 'Risk Alert',
  'card.advice': 'Advice',
  'card.forecast': 'Forecast',
  'action.askAi': 'Ask AI',
  'action.detail': 'View Details',
  'action.export': 'Export',
  'severity.LOW': 'Low',
  'severity.MEDIUM': 'Medium',
  'severity.HIGH': 'High',
  'severity.CRITICAL': 'Critical',
};

const DICTS: Record<Locale, Record<string, string>> = { 'zh-CN': ZH, en: EN };

let _locale: Locale = (uni.getStorageSync('locale') as Locale) || 'zh-CN';

export function t(key: string): string {
  return DICTS[_locale][key] || key;
}

export function setLocale(loc: Locale) {
  _locale = loc;
  uni.setStorageSync('locale', loc);
}

export function locale(): Locale { return _locale; }
