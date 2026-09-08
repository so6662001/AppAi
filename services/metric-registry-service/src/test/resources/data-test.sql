INSERT INTO metric_def
  (metric_code, name, name_zh, domain, formula, semantics, status, sensitivity, owner, version, requires_metrics)
VALUES
  ('M001', 'sales_amount', '销售额', 'SALES', 'SUM(order_amount)', 'additive', 'PUBLISHED', 'MEDIUM', '张三', '3.2.0', NULL),
  ('M006', 'gross_profit', '销售毛利', 'SALES', 'SUM(gross_profit)', 'additive', 'PUBLISHED', 'HIGH', '张三', '2.1.0', NULL),
  ('M120', 'net_profit', '销售净利润', 'SALES', 'contribution_margin - allocated_period_expense', 'virtual', 'PUBLISHED', 'HIGH', 'CFO', '2.0.0', '["M119"]');

INSERT INTO metric_usage_ref (metric_code, ref_type, ref_id_str, tenant_id)
VALUES ('M001', 'DASHBOARD', 'dashboard-1', 1),
       ('M001', 'AI_SESSION', 'sid-1', 1);

INSERT INTO sys_permission (perm_code, perm_name) VALUES
  ('metric.read', '读指标'),
  ('finance.read', '财务数据查看');

-- 预置 3 个 pack 用于测试
INSERT INTO metric_pack (pack_id, name, description, business_line, role_code,
    metrics_json, summary_kpis_json, popularity, metric_count, is_system, is_active)
VALUES
  ('PK_TRADE_OWNER', '老板包-钢贸', '老板视角', 'TRADE', 'OWNER',
   '"ALL"', '["sales_amount","ton_gross_profit","inv_amount","net_margin"]',
   100, 178, 1, 1),
  ('PK_TRADE_SALES_REP', '业务员包', '业务员视角', 'TRADE', 'SALES_REP',
   '["sales_amount","ton_gross_profit","ar_overdue_amount"]',
   '["sales_amount","ton_gross_profit","active_customer_count","ar_overdue_amount"]',
   50, 12, 1, 1),
  ('PK_TRADE_CFO', 'CFO 包', 'CFO 视角', 'TRADE', 'CFO',
   '["sales_amount","net_profit","net_margin","ar_outstanding"]',
   '["net_margin","ar_outstanding","customer_capital_occupation","ar_aging_overdue_rate"]',
   30, 25, 1, 1);
