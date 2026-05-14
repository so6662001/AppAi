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
