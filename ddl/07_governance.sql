-- =====================================================================
-- 指标治理 / 注册中心 / 审计
-- 物理库建议放 MySQL 而非 StarRocks (强事务 + 频繁更新)
-- 此文件给出 MySQL DDL
-- =====================================================================

CREATE DATABASE IF NOT EXISTS steel_governance DEFAULT CHARSET utf8mb4;
USE steel_governance;

-- ----------------------------- 指标主表 -----------------------------
CREATE TABLE IF NOT EXISTS metric_def (
  metric_code      VARCHAR(64)   NOT NULL,
  name             VARCHAR(128)  NOT NULL,
  name_zh          VARCHAR(128)  NOT NULL,
  domain           VARCHAR(32)   NOT NULL,            -- SALES/INVENTORY/...
  synonyms         JSON,
  fact             VARCHAR(128),
  formula          TEXT,
  semantics        VARCHAR(16),                       -- additive/snapshot/virtual/dimension
  time_agg         VARCHAR(16),
  format           VARCHAR(16),
  unit             VARCHAR(16),
  applicable       JSON,                              -- ["TRADE","PROCESS","MILL"]
  requires_metrics JSON,
  filter_expr      VARCHAR(512),
  join_tables      JSON,
  sensitivity      VARCHAR(8)    DEFAULT 'LOW',
  bizToken_multiplier DECIMAL(4,2) DEFAULT 1.00,
  owner            VARCHAR(64)   NOT NULL,
  steward          VARCHAR(64),
  approvers        JSON,
  version          VARCHAR(16)   NOT NULL,
  status           VARCHAR(16)   NOT NULL DEFAULT 'DRAFT',
  sla_freshness_minutes INT     DEFAULT 60,
  sla_availability DECIMAL(5,2)  DEFAULT 99.50,
  notes            TEXT,
  tags             JSON,
  created_at       DATETIME      DEFAULT CURRENT_TIMESTAMP,
  updated_at       DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (metric_code),
  KEY idx_domain (domain),
  KEY idx_owner  (owner),
  KEY idx_status (status)
) ENGINE=InnoDB;

-- ----------------------------- 指标版本历史 -----------------------------
CREATE TABLE IF NOT EXISTS metric_def_history (
  history_id   BIGINT        NOT NULL AUTO_INCREMENT,
  metric_code  VARCHAR(64)   NOT NULL,
  version      VARCHAR(16)   NOT NULL,
  status       VARCHAR(16),
  snapshot_json JSON,
  changed_by   VARCHAR(64),
  changed_at   DATETIME      DEFAULT CURRENT_TIMESTAMP,
  change_note  TEXT,
  PRIMARY KEY (history_id),
  KEY idx_code_version (metric_code, version)
) ENGINE=InnoDB;

-- ----------------------------- 变更申请 -----------------------------
CREATE TABLE IF NOT EXISTS metric_change_request (
  request_id     BIGINT        NOT NULL AUTO_INCREMENT,
  metric_code    VARCHAR(64),                         -- 新增时为空
  change_type    VARCHAR(16)   NOT NULL,              -- CREATE/FORMULA/RENAME/DEPRECATE/SLA/SYNONYM/OWNER
  from_version   VARCHAR(16),
  to_version     VARCHAR(16),
  payload_json   JSON,                                -- 新值
  diff_summary   TEXT,                                -- 差异说明
  impact_summary JSON,                                -- 影响分析: downstream_metrics, dashboards, sessions, billing
  status         VARCHAR(16)   DEFAULT 'DRAFT',       -- DRAFT/SUBMITTED/APPROVED/REJECTED/MERGED/CANCELED
  created_by     VARCHAR(64),
  created_at     DATETIME      DEFAULT CURRENT_TIMESTAMP,
  submitted_at   DATETIME,
  decided_at     DATETIME,
  merged_at      DATETIME,
  PRIMARY KEY (request_id),
  KEY idx_status (status),
  KEY idx_code   (metric_code)
) ENGINE=InnoDB;

-- ----------------------------- 审批 -----------------------------
CREATE TABLE IF NOT EXISTS metric_approval (
  approval_id BIGINT      NOT NULL AUTO_INCREMENT,
  request_id  BIGINT      NOT NULL,
  approver    VARCHAR(64) NOT NULL,
  decision    VARCHAR(16),                            -- APPROVED/REJECTED/REVISE
  comment     TEXT,
  decided_at  DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (approval_id),
  KEY idx_request (request_id)
) ENGINE=InnoDB;

-- ----------------------------- 订阅 -----------------------------
CREATE TABLE IF NOT EXISTS metric_subscription (
  sub_id      BIGINT      NOT NULL AUTO_INCREMENT,
  metric_code VARCHAR(64) NOT NULL,
  subscriber  VARCHAR(64) NOT NULL,
  notify_on   JSON,                                   -- ["FORMULA","DEPRECATE","SLA_BREACH"]
  channel     JSON,                                   -- ["EMAIL","DINGTALK","WECOM","INBOX"]
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (sub_id),
  UNIQUE KEY uk_sub (metric_code, subscriber)
) ENGINE=InnoDB;

-- ----------------------------- 数据质量监控记录 -----------------------------
CREATE TABLE IF NOT EXISTS metric_quality_event (
  event_id     BIGINT      NOT NULL AUTO_INCREMENT,
  metric_code  VARCHAR(64) NOT NULL,
  event_type   VARCHAR(32) NOT NULL,                   -- FRESHNESS/NULL_RATIO/SPIKE/CONSISTENCY/SLA
  severity     VARCHAR(8),
  detected_at  DATETIME,
  detail_json  JSON,
  resolved_at  DATETIME,
  PRIMARY KEY (event_id),
  KEY idx_code_time (metric_code, detected_at)
) ENGINE=InnoDB;

-- ----------------------------- 查询审计日志 -----------------------------
CREATE TABLE IF NOT EXISTS query_audit_log (
  audit_id     BIGINT      NOT NULL AUTO_INCREMENT,
  tenant_id    BIGINT      NOT NULL,
  user_id      BIGINT,
  session_id   VARCHAR(64),
  message_id   VARCHAR(64),
  dsl_json     JSON,
  sql_text     TEXT,
  tables_used  JSON,
  metrics_used JSON,
  est_rows     BIGINT,
  scan_rows    BIGINT,
  exec_ms      INT,
  cache_hit    TINYINT,
  error_code   VARCHAR(32),
  created_at   DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (audit_id),
  KEY idx_tenant_time (tenant_id, created_at)
) ENGINE=InnoDB;

-- ----------------------------- 看板/会话引用指标 (供影响分析) -----------------------------
CREATE TABLE IF NOT EXISTS metric_usage_ref (
  ref_id       BIGINT      NOT NULL AUTO_INCREMENT,
  metric_code  VARCHAR(64) NOT NULL,
  ref_type     VARCHAR(16) NOT NULL,    -- DASHBOARD/SAVED_QUERY/AI_SESSION/BILLING_RULE
  ref_id_str   VARCHAR(128) NOT NULL,
  ref_name     VARCHAR(256),
  tenant_id    BIGINT,
  updated_at   DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (ref_id),
  KEY idx_metric (metric_code),
  KEY idx_ref    (ref_type, ref_id_str)
) ENGINE=InnoDB;
