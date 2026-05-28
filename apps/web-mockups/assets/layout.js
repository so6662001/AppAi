/**
 * 共用 侧边栏 + 顶部 渲染脚本.
 * 用法: 在 body 顶部写 <div id="app-shell" data-active="ai-briefing.html"></div>, 引入本脚本即可.
 */
(function () {
  const MENUS = [
    { group: '经营驾驶舱', items: [
      { ico: '🏠', label: '老板看板',         href: 'dashboard-owner.html' },
      { ico: '📰', label: 'AI 经营早报',       href: 'ai-briefing.html', badge: '3' },
      { ico: '💬', label: 'AI 经营助手',       href: 'ai-chat.html' },
      { ico: '🔬', label: '指标钻取',         href: 'metric-drilldown.html' },
    ]},
    { group: '我的画像 · 智能教练', items: [
      { ico: '👑', label: '老板画像',         href: 'role-insight-owner.html' },
      { ico: '🎯', label: '销售部经理画像',   href: 'role-insight-sales-mgr.html' },
      { ico: '🤝', label: '销售员画像',       href: 'role-insight-sales-rep.html' },
      { ico: '🏭', label: '采购经理画像',     href: 'role-insight-purchasing-mgr.html' },
      { ico: '💼', label: '财务总监画像',     href: 'role-insight-finance.html' },
    ]},
    { group: '报表与预测', items: [
      { ico: '📊', label: '财务三表',         href: 'finance-statements.html' },
      { ico: '🏢', label: '多主体合并',       href: 'consolidation.html' },
      { ico: '📈', label: '期现结合看板',     href: 'hedge-board.html' },
    ]},
    { group: '人与提成', items: [
      { ico: '💰', label: '我的提成',         href: 'commission-detail.html' },
      { ico: '⚙️', label: '提成方案配置',     href: 'commission-config.html' },
    ]},
    { group: '合规与治理', items: [
      { ico: '🔍', label: '业务费/抹零审计',  href: 'biz-expense-audit.html' },
      { ico: '📑', label: '指标注册中心',     href: 'metric-registry.html' },
    ]},
    { group: '系统', items: [
      { ico: '🚀', label: '租户开户向导',     href: 'tenant-onboarding.html' },
      { ico: '🗂️', label: '原型导览',         href: 'index.html' },
    ]},
  ];

  const shell = document.getElementById('app-shell');
  if (!shell) return;
  const active = shell.dataset.active;
  const crumbs = shell.dataset.crumbs || '';
  const userName = shell.dataset.user || '张总';
  const userRole = shell.dataset.role || '演示·钢贸+加工综合体 · 总经理';

  let menuHtml = `
  <aside class="sidebar">
    <div class="brand"><div class="logo">钢</div><div class="name">钢铁AI<small>经营分析平台</small></div></div>`;
  MENUS.forEach(g => {
    menuHtml += `<div class="menu-group">${g.group}</div>`;
    g.items.forEach(it => {
      const cls = active === it.href ? 'menu-item active' : 'menu-item';
      menuHtml += `<a class="${cls}" href="./${it.href}"><span class="ico">${it.ico}</span>${it.label}` +
        (it.badge ? `<span class="badge">${it.badge}</span>` : '') + `</a>`;
    });
  });
  menuHtml += `</aside>`;

  const header = `
  <header class="header">
    <div class="crumbs">${crumbs}</div>
    <div class="search">🔍 <input placeholder="跟 AI 说: 上周吨毛利, 哪些客户该催收..."></div>
    <div class="tools">
      <div class="tool-btn">🌐</div>
      <div class="tool-btn">🛎️<span class="dot"></span></div>
      <div class="tool-btn">⚙️</div>
    </div>
    <div class="avatar"><div class="ph">${userName[0]}</div><div><div class="nm">${userName}</div><div class="rl">${userRole}</div></div></div>
  </header>`;

  shell.outerHTML = menuHtml + header;
})();
