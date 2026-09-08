-- 预置 2 个模板
INSERT INTO scheduled_report_template
  (business_line, role, category, name, description, dsl_json, cron_expr, channels, popularity, is_active)
VALUES
('TRADE', 'OWNER', 'DAILY', '老板日报-销售&库存',
 '每天 08:00 推送昨日核心',
 '{"metrics":["sales_amount","inv_amount"],"time":{"preset":"yesterday"}}',
 '0 0 8 * * ?', '["INAPP","WECOM"]', 100, 1),
('PROCESS', 'MANAGER', 'DAILY', '加工厂日报-OEE',
 '每天 07:30 昨日产线',
 '{"metrics":["oee","quality_rate"],"time":{"preset":"yesterday"}}',
 '0 30 7 * * ?', '["INAPP"]', 50, 1);
