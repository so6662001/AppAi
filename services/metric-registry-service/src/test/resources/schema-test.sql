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
