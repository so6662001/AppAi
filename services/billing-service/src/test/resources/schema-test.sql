-- H2 测试 schema (与 ddl/08_billing.sql 兼容简化)
DROP TABLE IF EXISTS tenant_wallet;
CREATE TABLE tenant_wallet (
  tenant_id BIGINT PRIMARY KEY,
  token_balance BIGINT DEFAULT 0,
  times_balance INT DEFAULT 0,
  sub_period_quota BIGINT DEFAULT 0,
  sub_period_used BIGINT DEFAULT 0,
  overrun_limit_cent INT DEFAULT 0,
  overrun_used_cent INT DEFAULT 0,
  overrun_price_cent_per_1k INT DEFAULT 40,
  version BIGINT DEFAULT 0,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS usage_reservation;
CREATE TABLE usage_reservation (
  reservation_id VARCHAR(40) PRIMARY KEY,
  tenant_id BIGINT,
  user_id BIGINT,
  session_id VARCHAR(40),
  message_id VARCHAR(40),
  estimate_tokens BIGINT,
  plan_json CLOB,
  status VARCHAR(16) DEFAULT 'HELD',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  settled_at TIMESTAMP,
  expires_at TIMESTAMP
);

DROP TABLE IF EXISTS usage_record;
CREATE TABLE usage_record (
  usage_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  user_id BIGINT,
  session_id VARCHAR(40),
  message_id VARCHAR(40),
  reservation_id VARCHAR(40),
  model_name VARCHAR(64),
  input_tokens INT,
  output_tokens INT,
  cache_hit TINYINT,
  query_rows INT,
  exec_ms INT,
  biz_tokens_charged BIGINT,
  bucket VARCHAR(16),
  cost_cny DECIMAL(12,4),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS billing_ledger;
CREATE TABLE billing_ledger (
  ledger_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  ref_type VARCHAR(16),
  ref_id VARCHAR(40),
  account VARCHAR(32),
  direction VARCHAR(4),
  amount BIGINT,
  unit VARCHAR(8),
  balance_after BIGINT,
  remark VARCHAR(256),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
