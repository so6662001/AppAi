DROP TABLE IF EXISTS metric_def;
CREATE TABLE metric_def (
  metric_code VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128),
  name_zh VARCHAR(128),
  domain VARCHAR(32),
  formula CLOB,
  semantics VARCHAR(16),
  status VARCHAR(16) DEFAULT 'DRAFT',
  sensitivity VARCHAR(8) DEFAULT 'LOW',
  owner VARCHAR(64),
  version VARCHAR(16),
  requires_metrics CLOB,
  notes CLOB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS metric_usage_ref;
CREATE TABLE metric_usage_ref (
  ref_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  metric_code VARCHAR(64),
  ref_type VARCHAR(16),
  ref_id_str VARCHAR(128),
  tenant_id BIGINT
);

-- RBAC 表
DROP TABLE IF EXISTS sys_user;
CREATE TABLE sys_user (
  user_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  username VARCHAR(64),
  display_name VARCHAR(128),
  email VARCHAR(128),
  phone VARCHAR(32),
  password_hash VARCHAR(128),
  is_active TINYINT DEFAULT 1,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
DROP TABLE IF EXISTS sys_role;
CREATE TABLE sys_role (
  role_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  role_code VARCHAR(32),
  role_name VARCHAR(64),
  is_active TINYINT DEFAULT 1
);
DROP TABLE IF EXISTS sys_user_role;
CREATE TABLE sys_user_role (
  user_id BIGINT, role_id BIGINT,
  PRIMARY KEY(user_id, role_id)
);
DROP TABLE IF EXISTS sys_permission;
CREATE TABLE sys_permission (
  perm_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  perm_code VARCHAR(64), perm_name VARCHAR(128)
);
DROP TABLE IF EXISTS sys_role_permission;
CREATE TABLE sys_role_permission (
  role_id BIGINT, perm_id BIGINT,
  PRIMARY KEY(role_id, perm_id)
);
DROP TABLE IF EXISTS sys_row_acl;
CREATE TABLE sys_row_acl (
  acl_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT,
  resource VARCHAR(32),
  resource_ids CLOB
);

DROP TABLE IF EXISTS metric_quality_event;
CREATE TABLE metric_quality_event (
  event_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  metric_code VARCHAR(64),
  event_type VARCHAR(32),
  severity VARCHAR(8),
  detected_at TIMESTAMP,
  detail_json CLOB,
  resolved_at TIMESTAMP
);

-- ============== metric_pack 相关 ==============
DROP TABLE IF EXISTS metric_pack;
CREATE TABLE metric_pack (
  pack_id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(128),
  description VARCHAR(512),
  business_line VARCHAR(16),
  role_code VARCHAR(32),
  metrics_json CLOB,
  summary_kpis_json CLOB,
  briefing_cards_json CLOB,
  recommended_questions_json CLOB,
  default_subscriptions_json CLOB,
  default_dashboard VARCHAR(128),
  is_active TINYINT DEFAULT 1,
  is_system TINYINT DEFAULT 1,
  metric_count INT DEFAULT 0,
  popularity INT DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS sys_user_preferences;
CREATE TABLE sys_user_preferences (
  user_id BIGINT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  business_line VARCHAR(16),
  primary_role VARCHAR(32),
  interests_json CLOB,
  custom_pack_ids CLOB,
  custom_metrics CLOB,
  onboarding_done TINYINT DEFAULT 0,
  onboarding_at TIMESTAMP,
  locale VARCHAR(8) DEFAULT 'zh-CN',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS sys_metric_apply;
CREATE TABLE sys_metric_apply (
  apply_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  tenant_id BIGINT NOT NULL,
  user_id BIGINT NOT NULL,
  metric_code VARCHAR(64),
  scope_code VARCHAR(64),
  reason CLOB,
  status VARCHAR(16) DEFAULT 'PENDING',
  reviewer_id BIGINT,
  review_comment VARCHAR(512),
  duration_days INT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  reviewed_at TIMESTAMP
);

DROP TABLE IF EXISTS sys_user_temp_grant;
CREATE TABLE sys_user_temp_grant (
  grant_id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  scope_code VARCHAR(64),
  metric_code VARCHAR(64),
  reason VARCHAR(256),
  granted_by BIGINT,
  granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP
);
