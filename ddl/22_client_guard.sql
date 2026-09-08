-- =====================================================================
-- 22_client_guard.sql  (MySQL, steel_governance 库)
-- ERP 客户端防 RPA / 防爬取:策略、遥测事件、导出申请与审批、设备
-- 配套:apps/erp-client-guard (C# SDK), services/client-guard-service
-- =====================================================================
USE steel_governance;

-- 1. 租户级防护策略(JSON 与 C# GuardPolicy 字段一一对应)
CREATE TABLE IF NOT EXISTS client_guard_policy (
  tenant_id        BIGINT       NOT NULL,
  version          INT          NOT NULL DEFAULT 1,
  policy_json      JSON         NOT NULL,
  updated_by       BIGINT       NULL,
  updated_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户端防护策略(阈值/权重/配额/进程名单/敏感列)';

-- 2. 客户端遥测事件(不含屏幕内容与业务数据)
CREATE TABLE IF NOT EXISTS client_guard_event (
  id               BIGINT       NOT NULL AUTO_INCREMENT,
  event_id         CHAR(32)     NOT NULL,
  tenant_id        BIGINT       NOT NULL,
  user_id          BIGINT       NOT NULL,
  device_id        VARCHAR(64)  NOT NULL DEFAULT '',
  session_id       CHAR(32)     NOT NULL DEFAULT '',
  side             VARCHAR(16)  NOT NULL DEFAULT 'local' COMMENT 'local=本机直装 / remote=RDS 会话内 ERP / launcher=本地 RDP 启动器',
  link_id          CHAR(16)     NULL COMMENT '启动器 ↔ 远程会话 绑定 id',
  client_name      VARCHAR(64)  NULL COMMENT '远程端: WTSClientName; 启动器端: 本机名',
  event_at         DATETIME(3)  NOT NULL,
  received_at      DATETIME(3)  NOT NULL DEFAULT CURRENT_TIMESTAMP(3),
  event_type       VARCHAR(32)  NOT NULL COMMENT 'signal/decision/level_change/export/export_decision/copy/challenge/heartbeat/error',
  signal_kind      VARCHAR(48)  NULL,
  weight           DECIMAL(8,2) NULL,
  client_score     DECIMAL(6,2) NOT NULL DEFAULT 0,
  client_level     VARCHAR(16)  NOT NULL DEFAULT 'Low',
  server_score     DECIMAL(6,2) NULL COMMENT '服务端独立评分',
  detail           VARCHAR(1024) NULL,
  breakdown_json   JSON         NULL,
  client_version   VARCHAR(32)  NULL,
  os               VARCHAR(128) NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_event (event_id),
  KEY idx_tenant_user_time (tenant_id, user_id, event_at),
  KEY idx_type_time (event_type, event_at),
  KEY idx_link (link_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户端防护遥测事件';

-- 2b. 自研 RDP 启动器 ↔ 远程会话 绑定(双端联动评分 / 未配对会话识别)
CREATE TABLE IF NOT EXISTS client_guard_session_link (
  link_id            CHAR(16)     NOT NULL,
  tenant_id          BIGINT       NOT NULL,
  user_id            BIGINT       NOT NULL,
  launcher_device_id VARCHAR(64)  NOT NULL COMMENT '本地启动器设备指纹(绑定后远程端沿用)',
  machine_name       VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '本地机器名(= 远程端看到的 WTSClientName)',
  ticket_nonce       CHAR(12)     NOT NULL DEFAULT '',
  ticket_expires_at  DATETIME     NULL,
  local_score        DECIMAL(6,2) NOT NULL DEFAULT 0 COMMENT '申请票据时的本地风险分',
  status             VARCHAR(16)  NOT NULL DEFAULT 'issued' COMMENT 'issued/bound/expired',
  remote_device_id   VARCHAR(64)  NULL,
  client_name        VARCHAR(64)  NULL,
  client_address     VARCHAR(64)  NULL,
  created_at         DATETIME(3)  NOT NULL,
  bound_at           DATETIME(3)  NULL,
  PRIMARY KEY (link_id),
  KEY idx_tenant_user_machine (tenant_id, user_id, machine_name, created_at),
  KEY idx_nonce (tenant_id, user_id, ticket_nonce)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='RDP 启动器与远程会话绑定';

-- 3. 导出申请 / 审批
CREATE TABLE IF NOT EXISTS client_guard_export_request (
  request_id       CHAR(32)     NOT NULL,
  tenant_id        BIGINT       NOT NULL,
  user_id          BIGINT       NOT NULL,
  device_id        VARCHAR(64)  NOT NULL DEFAULT '',
  data_set         VARCHAR(64)  NOT NULL,
  row_count        INT          NOT NULL,
  risk_score       DECIMAL(6,2) NOT NULL DEFAULT 0,
  reason           VARCHAR(255) NULL,
  status           VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/denied/expired/used',
  approver_id      BIGINT       NULL,
  approver_name    VARCHAR(64)  NULL,
  approve_note     VARCHAR(255) NULL,
  token            VARCHAR(512) NULL,
  token_expires_at DATETIME     NULL,
  used_at          DATETIME     NULL,
  created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  decided_at       DATETIME     NULL,
  PRIMARY KEY (request_id),
  KEY idx_tenant_status (tenant_id, status, created_at),
  KEY idx_user_time (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大批量导出申请与审批';

-- 4. 服务端配额账本(按天,独立于客户端)
CREATE TABLE IF NOT EXISTS client_guard_export_ledger (
  tenant_id        BIGINT       NOT NULL,
  user_id          BIGINT       NOT NULL,
  ledger_date      DATE         NOT NULL,
  export_count     INT          NOT NULL DEFAULT 0,
  row_total        BIGINT       NOT NULL DEFAULT 0,
  last_export_at   DATETIME     NULL,
  PRIMARY KEY (tenant_id, user_id, ledger_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户级导出配额账本';

-- 5. 设备与会话状态(服务端下发 lock / degrade)
CREATE TABLE IF NOT EXISTS client_guard_device (
  tenant_id        BIGINT       NOT NULL,
  user_id          BIGINT       NOT NULL,
  device_id        VARCHAR(64)  NOT NULL,
  first_seen_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  server_score     DECIMAL(6,2) NOT NULL DEFAULT 0,
  directive        VARCHAR(16)  NOT NULL DEFAULT 'none' COMMENT 'none/degrade/lock',
  directive_reason VARCHAR(255) NULL,
  directive_until  DATETIME     NULL,
  trusted          TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '管理员标记可信设备(降低误报)',
  PRIMARY KEY (tenant_id, user_id, device_id),
  KEY idx_directive (directive, directive_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='客户端设备与服务端指令';

-- 默认策略(与 C# GuardPolicy.Default 保持一致的关键字段;其余留空回落到 SDK 内置默认)
INSERT INTO client_guard_policy (tenant_id, version, policy_json) VALUES
(0, 1, JSON_OBJECT(
  'version', 1,
  'thresholds', JSON_OBJECT('elevated', 30, 'high', 60, 'critical', 85),
  'export_quota', JSON_OBJECT(
      'max_rows_per_export', 20000, 'max_exports_per_hour', 10, 'max_rows_per_day', 200000,
      'approval_threshold_rows', 5000, 'delay_min_ms', 0, 'delay_max_ms', 0, 'allowed_hours', JSON_ARRAY()),
  'uia_probe_per_minute', 40,
  'clipboard_burst_count', 10,
  'exclude_from_capture', TRUE,
  'accessibility_mode', FALSE,
  'sensitive_columns', JSON_ARRAY('customer_name','customer_phone','contact_phone','unit_price','gross_profit',
                                  'supplier_name','cost_price','commission','credit_limit','bank_account')
))
ON DUPLICATE KEY UPDATE version = version;
