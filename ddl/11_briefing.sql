-- =====================================================================
-- AI 经营早报 (放 MySQL steel_chat)
-- =====================================================================
USE steel_chat;

-- 早报卡片
CREATE TABLE IF NOT EXISTS briefing_card (
  card_id        BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id      BIGINT       NOT NULL,
  user_id        BIGINT       NOT NULL,
  biz_date       DATE         NOT NULL,
  card_type      VARCHAR(16)  NOT NULL,    -- SUMMARY/RISK/ADVICE/INSIGHT/ABC/FORECAST/CAPITAL/ANOMALY/RECOMMEND/BALANCE
  severity       VARCHAR(8),                -- LOW/MEDIUM/HIGH/CRITICAL
  rank_score     DECIMAL(8,4),
  title          VARCHAR(256),
  payload_json   JSON,
  source_metrics JSON,                      -- 引用指标编号, 供"追问 AI"
  actions_json   JSON,                      -- 卡片操作按钮
  ref_inbox_id   BIGINT,                    -- 关联 advice_inbox.inbox_id
  status         VARCHAR(16)  DEFAULT 'NEW',-- NEW/READ/ACTED/IGNORED
  expires_at     DATETIME,
  created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  read_at        DATETIME,
  acted_at       DATETIME,
  PRIMARY KEY (card_id),
  KEY idx_user_date (tenant_id, user_id, biz_date),
  KEY idx_severity   (severity, status)
) ENGINE=InnoDB;

-- 用户早报布局 (个性化)
CREATE TABLE IF NOT EXISTS briefing_layout (
  tenant_id    BIGINT      NOT NULL,
  user_id      BIGINT      NOT NULL,
  role         VARCHAR(32),
  cards        JSON,                       -- 想看哪些卡片类型: ["SUMMARY","RISK",...]
  kpi_metrics  JSON,                       -- SUMMARY 卡显示哪 4 个指标
  silence_from TIME,
  silence_to   TIME,
  thresholds   JSON,                       -- 变化阈值
  push_channels JSON,                      -- 各严重度的渠道偏好
  updated_at   DATETIME    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, user_id)
) ENGINE=InnoDB;

-- 早报卡片反馈
CREATE TABLE IF NOT EXISTS briefing_feedback (
  feedback_id BIGINT      NOT NULL AUTO_INCREMENT,
  card_id     BIGINT      NOT NULL,
  tenant_id   BIGINT      NOT NULL,
  user_id     BIGINT,
  vote        VARCHAR(8),                  -- UP/DOWN
  reason      VARCHAR(32),                 -- NOT_USEFUL/WRONG/TOO_NOISY/OTHER
  remark      TEXT,
  created_at  DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (feedback_id),
  KEY idx_card (card_id)
) ENGINE=InnoDB;

-- 早报度量(产品本身的运营指标)
CREATE TABLE IF NOT EXISTS briefing_metrics_daily (
  biz_date        DATE        NOT NULL,
  tenant_id       BIGINT      NOT NULL,
  card_type       VARCHAR(16) NOT NULL,
  show_count      INT,
  click_count     INT,
  act_count       INT,
  ignore_count    INT,
  up_vote_count   INT,
  down_vote_count INT,
  avg_read_seconds DECIMAL(8,2),
  PRIMARY KEY (biz_date, tenant_id, card_type)
) ENGINE=InnoDB;

-- 推送下行记录(可观测/限流)
CREATE TABLE IF NOT EXISTS push_log (
  log_id      BIGINT      NOT NULL AUTO_INCREMENT,
  tenant_id   BIGINT      NOT NULL,
  user_id     BIGINT      NOT NULL,
  card_id     BIGINT,
  channel     VARCHAR(16),                 -- INAPP/UNI_PUSH/WECOM/DINGTALK/WECHAT/SMS/CALL
  severity    VARCHAR(8),
  status      VARCHAR(16),                 -- SENT/FAILED/SUPPRESSED
  reason      VARCHAR(64),                 -- 失败/抑制原因
  payload     JSON,
  sent_at     DATETIME    DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_user_time (tenant_id, user_id, sent_at)
) ENGINE=InnoDB;
