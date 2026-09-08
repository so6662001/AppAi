-- H2 测试库 schema (MySQL 兼容模式)
DROP TABLE IF EXISTS scheduled_report;
CREATE TABLE scheduled_report (
  report_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  name VARCHAR(128) NOT NULL,
  description VARCHAR(512),
  dsl_json CLOB,
  question VARCHAR(512),
  render_blocks CLOB,
  chart_spec CLOB,
  schedule_type VARCHAR(16) NOT NULL DEFAULT 'cron',
  cron_expr VARCHAR(64),
  timezone VARCHAR(32) DEFAULT 'Asia/Shanghai',
  next_run_at TIMESTAMP,
  last_run_at TIMESTAMP,
  fail_count INT DEFAULT 0,
  status VARCHAR(16) DEFAULT 'ACTIVE',
  recipients CLOB,
  channels CLOB NOT NULL,
  push_silent_if_empty TINYINT DEFAULT 0,
  push_format VARCHAR(16) DEFAULT 'card',
  notify_template VARCHAR(64),
  effective_from DATE,
  effective_to DATE,
  max_run_count INT,
  cost_owner_user_id BIGINT,
  estimated_biz_tokens BIGINT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  source VARCHAR(16) DEFAULT 'manual'
);

DROP TABLE IF EXISTS scheduled_report_run;
CREATE TABLE scheduled_report_run (
  run_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  report_id BIGINT NOT NULL,
  tenant_id BIGINT NOT NULL,
  scheduled_at TIMESTAMP NOT NULL,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  duration_ms INT,
  status VARCHAR(16) NOT NULL DEFAULT 'PENDING',
  error_code VARCHAR(32),
  error_msg VARCHAR(1024),
  sql_text CLOB,
  rows_returned INT,
  blocks_json CLOB,
  result_summary VARCHAR(1024),
  result_artifact_url VARCHAR(512),
  push_results CLOB,
  biz_tokens_charged BIGINT,
  cost_cny DECIMAL(12,4),
  reservation_id VARCHAR(40),
  message_id VARCHAR(40)
);

DROP TABLE IF EXISTS scheduled_report_template;
CREATE TABLE scheduled_report_template (
  template_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  business_line VARCHAR(16),
  role VARCHAR(32),
  category VARCHAR(32),
  name VARCHAR(128) NOT NULL,
  description VARCHAR(512),
  dsl_json CLOB NOT NULL,
  cron_expr VARCHAR(64),
  channels CLOB,
  popularity INT DEFAULT 0,
  is_active TINYINT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS tenant_notify_config;
CREATE TABLE tenant_notify_config (
  config_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  channel VARCHAR(16) NOT NULL,
  name VARCHAR(128),
  config_json CLOB NOT NULL,
  is_default TINYINT DEFAULT 0,
  is_active TINYINT DEFAULT 1,
  tags CLOB,
  created_by VARCHAR(64),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
