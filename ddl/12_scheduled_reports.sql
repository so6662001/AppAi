-- =====================================================================
-- 定时报表 (放 MySQL steel_chat)
-- 用户可把 AI 对话/DSL 查询另存为定时任务, 后台自动执行并推送结果
-- =====================================================================
USE steel_chat;

-- ----------------------------- 定时报表定义 -----------------------------
CREATE TABLE IF NOT EXISTS scheduled_report (
  report_id       BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id       BIGINT       NOT NULL,
  user_id         BIGINT       NOT NULL,                  -- 创建者
  name            VARCHAR(128) NOT NULL,                  -- 用户起的名字
  description     VARCHAR(512),

  -- ============ 查询定义 ============
  dsl_json        JSON         NOT NULL,                  -- DSL: metrics/dimensions/filters/time...
  question        VARCHAR(512),                           -- 原始自然语言提问(可选)
  render_blocks   JSON,                                   -- 期望渲染的块: ['kpi','table','chart','summary']
  chart_spec      JSON,                                   -- 图表配置(类型/X/Y轴)

  -- ============ 调度 ============
  schedule_type   VARCHAR(16)  NOT NULL DEFAULT 'cron',   -- cron / interval / daily / weekly / monthly / once
  cron_expr       VARCHAR(64),                            -- 标准 6 段 cron, eg "0 0 8 * * ?"
  timezone        VARCHAR(32)  DEFAULT 'Asia/Shanghai',
  next_run_at     DATETIME,                               -- 下次触发时间(调度器维护)
  last_run_at     DATETIME,                               -- 上次成功触发时间
  fail_count      INT          DEFAULT 0,                 -- 连续失败次数, >=3 自动暂停
  status          VARCHAR(16)  DEFAULT 'ACTIVE',          -- ACTIVE / PAUSED / EXPIRED / DELETED

  -- ============ 推送 ============
  recipients      JSON,                                   -- ["user:1","user:2","role:sales_manager"]
  channels        JSON         NOT NULL,                  -- ["INAPP","WECOM","DINGTALK","EMAIL","UNI_PUSH"]
  push_silent_if_empty TINYINT DEFAULT 0,                 -- 无数据时是否静默
  push_format     VARCHAR(16)  DEFAULT 'card',            -- card / table / image / excel
  notify_template VARCHAR(64),                            -- 模板 id (公众号模板消息)

  -- ============ 生命周期 ============
  effective_from  DATE,
  effective_to    DATE,                                   -- 到期自动 EXPIRED
  max_run_count   INT,                                    -- 总执行次数上限, 达到自动 EXPIRED

  -- ============ 计费 ============
  cost_owner_user_id BIGINT,                              -- 谁出 Token (默认创建者)
  estimated_biz_tokens BIGINT,

  -- ============ 审计 ============
  created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  source          VARCHAR(16)  DEFAULT 'chat',            -- chat / manual / template

  PRIMARY KEY (report_id),
  KEY idx_status_next (status, next_run_at),
  KEY idx_tenant_user (tenant_id, user_id)
) ENGINE=InnoDB COMMENT='定时报表定义';


-- ----------------------------- 每次执行记录 -----------------------------
CREATE TABLE IF NOT EXISTS scheduled_report_run (
  run_id          BIGINT       NOT NULL AUTO_INCREMENT,
  report_id       BIGINT       NOT NULL,
  tenant_id       BIGINT       NOT NULL,
  scheduled_at    DATETIME     NOT NULL,                  -- 应该触发的时间
  started_at      DATETIME,
  finished_at     DATETIME,
  duration_ms     INT,
  status          VARCHAR(16)  NOT NULL DEFAULT 'PENDING',-- PENDING/RUNNING/SUCCESS/FAILED/EMPTY/CANCELED
  error_code      VARCHAR(32),
  error_msg       VARCHAR(1024),

  sql_text        MEDIUMTEXT,
  rows_returned   INT,
  blocks_json     JSON,                                   -- 渲染好的结果块(供 uniapp 直接展示)
  result_summary  VARCHAR(1024),                          -- AI 生成的一句话总结
  result_artifact_url VARCHAR(512),                       -- 大数据走对象存储

  push_results    JSON,                                   -- [{channel,status,latency_ms,error}]

  -- 计费
  biz_tokens_charged BIGINT,
  cost_cny        DECIMAL(12,4),
  reservation_id  VARCHAR(40),

  message_id      VARCHAR(40),                            -- 同步落到 chat_message, 让用户在会话页能看到

  PRIMARY KEY (run_id),
  KEY idx_report_time (report_id, scheduled_at),
  KEY idx_tenant_status (tenant_id, status)
) ENGINE=InnoDB COMMENT='定时报表执行历史'
  PARTITION BY RANGE (TO_DAYS(scheduled_at)) (
    PARTITION p2026_05 VALUES LESS THAN (TO_DAYS('2026-06-01')),
    PARTITION p2026_06 VALUES LESS THAN (TO_DAYS('2026-07-01'))
    /* 后续按月预创建 */
  );


-- ----------------------------- 订阅他人报表 (可选共享) -----------------------------
CREATE TABLE IF NOT EXISTS scheduled_report_subscription (
  sub_id          BIGINT       NOT NULL AUTO_INCREMENT,
  report_id       BIGINT       NOT NULL,
  tenant_id       BIGINT       NOT NULL,
  subscriber_user_id BIGINT    NOT NULL,
  channels        JSON,                                   -- 该订阅者的渠道偏好 (覆盖 report 默认)
  status          VARCHAR(16)  DEFAULT 'ACTIVE',          -- ACTIVE / MUTED / UNSUBSCRIBED
  created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (sub_id),
  UNIQUE KEY uk_report_user (report_id, subscriber_user_id)
) ENGINE=InnoDB;


-- ----------------------------- 报表模板 (运营预置) -----------------------------
CREATE TABLE IF NOT EXISTS scheduled_report_template (
  template_id     BIGINT       NOT NULL AUTO_INCREMENT,
  business_line   VARCHAR(16),                           -- TRADE/PROCESS/MILL/ALL
  role            VARCHAR(32),                           -- OWNER/SALES/MANAGER...
  category        VARCHAR(32),                           -- DAILY/WEEKLY/MONTHLY
  name            VARCHAR(128) NOT NULL,
  description     VARCHAR(512),
  dsl_json        JSON         NOT NULL,
  cron_expr       VARCHAR(64),
  channels        JSON,
  popularity      INT          DEFAULT 0,                -- 被订阅次数
  is_active       TINYINT      DEFAULT 1,
  created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (template_id),
  KEY idx_line_role (business_line, role, category)
) ENGINE=InnoDB;


-- ----------------------------- 预置一批通用模板 -----------------------------
INSERT INTO scheduled_report_template
  (business_line, role, category, name, description, dsl_json, cron_expr, channels) VALUES
('TRADE', 'OWNER',   'DAILY', '老板日报-销售&库存',
 '每天 08:00 推送昨日核心指标',
 '{"metrics":["sales_amount","sales_tonnage","ton_gross_profit","inv_amount","ar_outstanding"],"time":{"preset":"yesterday","grain":"day"},"compare":{"mode":"wow"}}',
 '0 0 8 * * ?', '["INAPP","WECOM"]'),

('TRADE', 'OWNER',   'DAILY', '老板日报-资金占用 Top10',
 '每天 08:00 推送资金占用最高的 10 个客户',
 '{"metrics":["customer_capital_occupation","customer_irr"],"dimensions":["customer"],"time":{"preset":"yesterday"},"orderBy":[{"field":"customer_capital_occupation","dir":"desc"}],"limit":10}',
 '0 5 8 * * ?', '["INAPP","WECOM"]'),

('TRADE', 'OWNER',   'WEEKLY','周报-毛利与挂价让利',
 '每周一 08:00 推送上周毛利结构',
 '{"metrics":["gross_profit","ton_gross_profit","listed_vs_actual_gap"],"dimensions":["org.region","material.product_type"],"time":{"preset":"last_week","grain":"day"},"compare":{"mode":"wow"}}',
 '0 0 8 ? * MON', '["INAPP","EMAIL"]'),

('TRADE', 'SALES',   'DAILY', '业务员日报-我的销售',
 '每天 18:00 推送当日个人业绩',
 '{"metrics":["sales_amount","ton_gross_profit","ar_overdue_amount"],"filters":[{"field":"sales_owner.employee_id","op":"=","value":"{user_id}"}],"time":{"preset":"today"}}',
 '0 0 18 * * ?', '["INAPP","UNI_PUSH"]'),

('PROCESS','MANAGER','DAILY','加工厂日报-OEE&工单',
 '每天 07:30 推送昨日产线运行',
 '{"metrics":["oee","availability","performance","quality_rate","wo_overdue_rate"],"dimensions":["workcenter"],"time":{"preset":"yesterday"}}',
 '0 30 7 * * ?', '["INAPP","DINGTALK"]'),

('PROCESS','MANAGER','DAILY','加工厂日报-良率&能耗',
 '每天 07:30 推送昨日质量与能耗',
 '{"metrics":["ftq","scrap_rate","material_utilization","energy_per_ton"],"dimensions":["workcenter"],"time":{"preset":"yesterday"}}',
 '0 35 7 * * ?', '["INAPP"]'),

('MILL',   'MANAGER','DAILY','钢厂日报-产量&吨钢成本',
 '每天 07:00 推送昨日产量、吨钢成本',
 '{"metrics":["melt_tonnage","hot_rolling_tonnage","cold_rolling_tonnage","cost_per_ton","energy_per_ton"],"time":{"preset":"yesterday"}}',
 '0 0 7 * * ?', '["INAPP","WECOM"]'),

('MILL',   'OWNER',  'MONTHLY','月度财务-净利率&吨净利',
 '每月 1 日 09:00 推送上月净利',
 '{"metrics":["net_profit","net_margin","ton_net_profit"],"dimensions":["org.region"],"time":{"preset":"last_month","grain":"month"},"compare":{"mode":"mom"}}',
 '0 0 9 1 * ?', '["INAPP","EMAIL"]'),

('TRADE', 'OWNER',   'WEEKLY','周报-库存预警',
 '每周一 08:00 推送呆滞与缺货 SKU',
 '{"metrics":["aging_365_plus_amount","long_tail_inv_amount","dead_stock_amount","spec_oos_count"],"time":{"preset":"last_week"}}',
 '0 0 8 ? * MON', '["INAPP"]'),

('TRADE', 'OWNER',   'DAILY', '风控日报-客户授信',
 '每天 07:30 推送授信使用率高的客户',
 '{"metrics":["credit_utilization_rate","credit_overlimit_amount","customer_risk_score"],"dimensions":["customer"],"filters":[{"field":"credit_utilization_rate","op":">","value":0.8}],"time":{"preset":"yesterday"},"orderBy":[{"field":"credit_utilization_rate","dir":"desc"}],"limit":20}',
 '0 30 7 * * ?', '["INAPP","WECOM"]');
