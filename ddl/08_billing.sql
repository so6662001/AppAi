-- =====================================================================
-- 计费 / 钱包 / 用量 (放 MySQL, 强事务)
-- =====================================================================
CREATE DATABASE IF NOT EXISTS steel_billing DEFAULT CHARSET utf8mb4;
USE steel_billing;

-- ----------------------------- 套餐 -----------------------------
CREATE TABLE IF NOT EXISTS billing_plan (
  plan_id              BIGINT       NOT NULL AUTO_INCREMENT,
  plan_code            VARCHAR(32)  NOT NULL UNIQUE,    -- TOKEN_500W / SUB_PRO / TIMES_1000
  plan_type            VARCHAR(16)  NOT NULL,           -- TOKEN_PACK / SUBSCRIPTION / TIMES_PACK
  name                 VARCHAR(128) NOT NULL,
  description          TEXT,
  price_cny            DECIMAL(12,2) NOT NULL,
  duration_days        INT,                             -- 仅订阅
  included_biz_tokens  BIGINT       DEFAULT 0,
  included_times       INT          DEFAULT 0,
  overrun_price_cny_per_1k DECIMAL(10,4) DEFAULT 0.4,
  overrun_limit_cny    DECIMAL(12,2) DEFAULT 0,
  rules_json           JSON,
  is_active            TINYINT      DEFAULT 1,
  created_at           DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (plan_id),
  KEY idx_type (plan_type, is_active)
) ENGINE=InnoDB;

-- ----------------------------- 租户钱包 -----------------------------
CREATE TABLE IF NOT EXISTS tenant_wallet (
  tenant_id           BIGINT       NOT NULL,
  token_balance       BIGINT       DEFAULT 0,
  times_balance       INT          DEFAULT 0,
  sub_plan_id         BIGINT,
  sub_start           DATE,
  sub_end             DATE,
  sub_period_quota    BIGINT       DEFAULT 0,
  sub_period_used     BIGINT       DEFAULT 0,
  overrun_limit_cent  INT          DEFAULT 0,
  overrun_used_cent   INT          DEFAULT 0,
  overrun_price_cent_per_1k INT    DEFAULT 40,         -- 分/千 biz token
  version             BIGINT       DEFAULT 0,
  updated_at          DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id)
) ENGINE=InnoDB;

-- ----------------------------- 订阅 -----------------------------
CREATE TABLE IF NOT EXISTS billing_subscription (
  sub_id           BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id        BIGINT       NOT NULL,
  plan_id          BIGINT       NOT NULL,
  start_date       DATE,
  end_date         DATE,
  auto_renew       TINYINT      DEFAULT 0,
  status           VARCHAR(16)  DEFAULT 'ACTIVE',     -- ACTIVE/EXPIRED/CANCELED
  created_at       DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (sub_id),
  KEY idx_tenant (tenant_id),
  KEY idx_status (status, end_date)
) ENGINE=InnoDB;

-- ----------------------------- 购买订单 -----------------------------
CREATE TABLE IF NOT EXISTS billing_order (
  order_id        BIGINT       NOT NULL AUTO_INCREMENT,
  order_no        VARCHAR(64)  UNIQUE,
  tenant_id       BIGINT       NOT NULL,
  plan_id         BIGINT       NOT NULL,
  pay_amount      DECIMAL(12,2),
  pay_status      VARCHAR(16),                        -- PENDING/PAID/REFUND/FAIL
  pay_channel     VARCHAR(32),                        -- WECHAT/ALIPAY/BANK
  pay_trade_no    VARCHAR(64),
  paid_at         DATETIME,
  effective_at    DATETIME,
  expire_at       DATETIME,
  invoice_status  VARCHAR(16)  DEFAULT 'NONE',
  created_at      DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (order_id),
  KEY idx_tenant (tenant_id, created_at)
) ENGINE=InnoDB;

-- ----------------------------- 预扣占用 -----------------------------
CREATE TABLE IF NOT EXISTS usage_reservation (
  reservation_id   VARCHAR(40)  NOT NULL,
  tenant_id        BIGINT       NOT NULL,
  user_id          BIGINT,
  session_id       VARCHAR(40),
  message_id       VARCHAR(40),
  estimate_tokens  BIGINT,
  plan_json        JSON,                              -- 多桶顺序占用计划
  status           VARCHAR(16)  NOT NULL DEFAULT 'HELD', -- HELD/SETTLED/RELEASED/EXPIRED
  created_at       DATETIME     DEFAULT CURRENT_TIMESTAMP,
  settled_at       DATETIME,
  expires_at       DATETIME,
  PRIMARY KEY (reservation_id),
  KEY idx_status_exp (status, expires_at)
) ENGINE=InnoDB;

-- ----------------------------- 用量明细 (按月分区/分表) -----------------------------
CREATE TABLE IF NOT EXISTS usage_record (
  usage_id            BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id           BIGINT       NOT NULL,
  user_id             BIGINT,
  session_id          VARCHAR(40),
  message_id          VARCHAR(40),
  reservation_id      VARCHAR(40),
  model_name          VARCHAR(64),
  input_tokens        INT,
  output_tokens       INT,
  cache_hit           TINYINT,
  query_rows          INT,
  exec_ms             INT,
  biz_tokens_charged  BIGINT,
  bucket              VARCHAR(16),                    -- SUB/TIMES/TOKEN/OVERRUN
  cost_cny            DECIMAL(12,4),
  created_at          DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (usage_id),
  UNIQUE KEY uk_msg (tenant_id, message_id),
  KEY idx_tenant_time (tenant_id, created_at)
) ENGINE=InnoDB
  PARTITION BY RANGE (TO_DAYS(created_at)) (
    PARTITION p2026_05 VALUES LESS THAN (TO_DAYS('2026-06-01')),
    PARTITION p2026_06 VALUES LESS THAN (TO_DAYS('2026-07-01'))
    /* 后续按月预创建分区 */
  );

-- ----------------------------- 账本 -----------------------------
CREATE TABLE IF NOT EXISTS billing_ledger (
  ledger_id      BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id      BIGINT       NOT NULL,
  ref_type       VARCHAR(16)  NOT NULL,                -- ORDER/USAGE/ADJUST/REFUND
  ref_id         VARCHAR(40)  NOT NULL,
  account        VARCHAR(32)  NOT NULL,                -- TOKEN_BALANCE/TIMES_BALANCE/SUB_QUOTA/OVERRUN
  direction      VARCHAR(4)   NOT NULL,                -- DR/CR
  amount         BIGINT       NOT NULL,
  unit           VARCHAR(8)   NOT NULL,                -- TOKEN/TIMES/CENT
  balance_after  BIGINT,
  remark         VARCHAR(256),
  created_at     DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (ledger_id),
  KEY idx_tenant_acct_time (tenant_id, account, created_at),
  KEY idx_ref   (ref_type, ref_id)
) ENGINE=InnoDB;

-- ----------------------------- 日聚合(看板用) -----------------------------
CREATE TABLE IF NOT EXISTS usage_daily_summary (
  tenant_id      BIGINT      NOT NULL,
  biz_date       DATE        NOT NULL,
  qa_count       INT,
  biz_tokens     BIGINT,
  cost_cny       DECIMAL(12,4),
  cache_hit_rate DECIMAL(5,4),
  PRIMARY KEY (tenant_id, biz_date)
) ENGINE=InnoDB;

-- ----------------------------- 对账差异 -----------------------------
CREATE TABLE IF NOT EXISTS billing_recon_diff (
  diff_id     BIGINT      NOT NULL AUTO_INCREMENT,
  tenant_id   BIGINT      NOT NULL,
  account     VARCHAR(32) NOT NULL,
  cache_bal   BIGINT,
  ledger_bal  BIGINT,
  diff_amount BIGINT,
  detected_at DATETIME    DEFAULT CURRENT_TIMESTAMP,
  fixed_at    DATETIME,
  fix_method  VARCHAR(32),
  PRIMARY KEY (diff_id),
  KEY idx_tenant_time (tenant_id, detected_at)
) ENGINE=InnoDB;

-- ----------------------------- 异步事件 Outbox -----------------------------
CREATE TABLE IF NOT EXISTS billing_outbox (
  outbox_id        BIGINT       NOT NULL AUTO_INCREMENT,
  event_type       VARCHAR(32)  NOT NULL,
  idempotency_key  VARCHAR(64)  NOT NULL,
  payload          JSON,
  status           VARCHAR(16)  DEFAULT 'PENDING',     -- PENDING/SENT/FAILED
  retries          INT          DEFAULT 0,
  next_retry_at    DATETIME,
  created_at       DATETIME     DEFAULT CURRENT_TIMESTAMP,
  sent_at          DATETIME,
  PRIMARY KEY (outbox_id),
  UNIQUE KEY uk_evt (event_type, idempotency_key),
  KEY idx_status_retry (status, next_retry_at)
) ENGINE=InnoDB;
