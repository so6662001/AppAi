-- =====================================================================
-- 聊天会话 / 反馈 / 推荐问题
-- =====================================================================
CREATE DATABASE IF NOT EXISTS steel_chat DEFAULT CHARSET utf8mb4;
USE steel_chat;

CREATE TABLE IF NOT EXISTS chat_session (
  session_id     VARCHAR(40)  NOT NULL,
  tenant_id      BIGINT       NOT NULL,
  user_id        BIGINT       NOT NULL,
  title          VARCHAR(256),
  pinned         TINYINT      DEFAULT 0,
  tags           JSON,
  business_line  VARCHAR(16),       -- TRADE/PROCESS/MILL
  role           VARCHAR(32),
  created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_message_at DATETIME,
  is_deleted     TINYINT      DEFAULT 0,
  PRIMARY KEY (session_id),
  KEY idx_tenant_user (tenant_id, user_id, updated_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_message (
  message_id     VARCHAR(40)  NOT NULL,
  session_id     VARCHAR(40)  NOT NULL,
  tenant_id      BIGINT       NOT NULL,
  user_id        BIGINT,
  role           VARCHAR(16)  NOT NULL,    -- user / assistant / system / tool
  content_text   MEDIUMTEXT,
  blocks_json    JSON,                     -- KPI/Chart/Table/Drilldown 等渲染块
  dsl_json       JSON,
  sql_text       MEDIUMTEXT,
  metrics_used   JSON,
  usage_input_tokens  INT,
  usage_output_tokens INT,
  usage_biz_tokens    BIGINT,
  usage_cost_cny  DECIMAL(12,4),
  usage_bucket    VARCHAR(16),
  model_name     VARCHAR(64),
  cache_hit      TINYINT,
  status         VARCHAR(16),              -- DRAFT/STREAMING/DONE/ERROR/CANCELED
  error_code     VARCHAR(32),
  error_msg      VARCHAR(512),
  parent_message_id VARCHAR(40),
  created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (message_id),
  KEY idx_session_time (session_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_feedback (
  feedback_id   BIGINT       NOT NULL AUTO_INCREMENT,
  message_id    VARCHAR(40)  NOT NULL,
  tenant_id     BIGINT       NOT NULL,
  user_id       BIGINT,
  vote          VARCHAR(8),                -- UP/DOWN
  reason        VARCHAR(32),               -- WRONG_DATA/UNCLEAR/NOT_WHAT_I_WANT/OTHER
  remark        TEXT,
  created_at    DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (feedback_id),
  KEY idx_msg (message_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS chat_recommended_question (
  rec_id        BIGINT       NOT NULL AUTO_INCREMENT,
  business_line VARCHAR(16),
  role          VARCHAR(32),
  category      VARCHAR(32),
  question      VARCHAR(256),
  dsl_template  JSON,
  rank_score    DECIMAL(8,4) DEFAULT 0,
  is_active     TINYINT      DEFAULT 1,
  PRIMARY KEY (rec_id),
  KEY idx_role (business_line, role, is_active)
) ENGINE=InnoDB;
