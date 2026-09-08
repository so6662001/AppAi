-- =====================================================================
-- 角色化指标包 + 用户偏好 + 临时授权 + 权限申请
-- 解决: 不同角色看不同指标 + 新用户上手引导
-- =====================================================================
USE steel_governance;

-- ----------------------------- 指标包 -----------------------------
CREATE TABLE IF NOT EXISTS metric_pack (
  pack_id           VARCHAR(64)  NOT NULL,        -- PK_SALES_REP_TRADE
  name              VARCHAR(128) NOT NULL,
  description       VARCHAR(512),
  business_line     VARCHAR(16),                  -- TRADE/PROCESS/MILL/ALL
  role_code         VARCHAR(32),                  -- 默认绑定到哪个角色
  metrics_json      JSON         NOT NULL,        -- ["sales_amount","gross_profit",...]
  summary_kpis_json JSON,                         -- 早报 SUMMARY 卡 4 个 KPI
  briefing_cards_json JSON,                       -- 默认早报卡片类型 ["SUMMARY","RISK","ADVICE"]
  recommended_questions_json JSON,                -- 10 条角色化推荐问题
  default_subscriptions_json JSON,                -- 默认订阅的报表模板 id 列表
  default_dashboard VARCHAR(128),                 -- 默认看板路径
  is_active         TINYINT      DEFAULT 1,
  is_system         TINYINT      DEFAULT 1,       -- 系统预置(1)/自定义(0)
  metric_count      INT          DEFAULT 0,
  popularity        INT          DEFAULT 0,       -- 被多少用户使用
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (pack_id),
  KEY idx_line_role (business_line, role_code, is_active)
) ENGINE=InnoDB COMMENT='角色化指标包';

-- ----------------------------- 角色-指标包绑定 (多对多) -----------------------------
CREATE TABLE IF NOT EXISTS sys_role_metric_pack (
  role_id    BIGINT       NOT NULL,
  pack_id    VARCHAR(64)  NOT NULL,
  is_primary TINYINT      DEFAULT 1,            -- 是否主包 (用于默认推荐)
  added_at   DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_id, pack_id),
  KEY idx_pack (pack_id)
) ENGINE=InnoDB;

-- ----------------------------- 用户偏好 (Onboarding 结果) -----------------------------
CREATE TABLE IF NOT EXISTS sys_user_preferences (
  user_id           BIGINT       NOT NULL,
  tenant_id         BIGINT       NOT NULL,
  business_line     VARCHAR(16),
  primary_role      VARCHAR(32),                -- Onboarding 选的角色
  interests_json    JSON,                       -- 用户勾选的关注领域 ["销售","客户","应收"]
  custom_pack_ids   JSON,                       -- 用户自订阅的额外 pack
  custom_metrics    JSON,                       -- 个人 watch list (额外关注的指标 code)
  onboarding_done   TINYINT      DEFAULT 0,
  onboarding_at     DATETIME,
  locale            VARCHAR(8)   DEFAULT 'zh-CN',
  push_silent_from  TIME         DEFAULT '22:00:00',
  push_silent_to    TIME         DEFAULT '08:00:00',
  updated_at        DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (user_id),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB COMMENT='用户个人偏好与 Onboarding 结果';

-- ----------------------------- 临时授权 -----------------------------
CREATE TABLE IF NOT EXISTS sys_user_temp_grant (
  grant_id    BIGINT       NOT NULL AUTO_INCREMENT,
  user_id     BIGINT       NOT NULL,
  scope_code  VARCHAR(64)  NOT NULL,           -- finance.profit.read
  metric_code VARCHAR(64),                     -- 可选: 仅授权某指标
  reason      VARCHAR(256),
  granted_by  BIGINT,                          -- 谁批的
  granted_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
  expires_at  DATETIME     NOT NULL,
  revoked_at  DATETIME,
  PRIMARY KEY (grant_id),
  KEY idx_user_active (user_id, expires_at, revoked_at)
) ENGINE=InnoDB COMMENT='临时权限授予 (例如审计期 30 天)';

-- ----------------------------- 权限申请 -----------------------------
CREATE TABLE IF NOT EXISTS sys_metric_apply (
  apply_id    BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id   BIGINT       NOT NULL,
  user_id     BIGINT       NOT NULL,
  metric_code VARCHAR(64),                     -- 想看的指标
  scope_code  VARCHAR(64),                     -- 想要的权限点
  reason      TEXT,
  status      VARCHAR(16)  DEFAULT 'PENDING',  -- PENDING/APPROVED/REJECTED
  reviewer_id BIGINT,
  review_comment VARCHAR(512),
  duration_days INT,                           -- 临时授权天数 (NULL=永久)
  created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME,
  PRIMARY KEY (apply_id),
  KEY idx_user_status (user_id, status),
  KEY idx_pending (status, created_at)
) ENGINE=InnoDB COMMENT='用户申请扩展权限';

-- ----------------------------- 预置 25 个角色 -----------------------------
INSERT INTO sys_role (tenant_id, role_code, role_name, is_active) VALUES
-- 通用
(0, 'OWNER',              '老板/总经理',       1),
(0, 'ADMIN',              '系统管理员',        1),
(0, 'DATA_STEWARD',       '数据负责人',        1),
(0, 'AUDITOR',            '审计员',           1),
-- TRADE 钢贸
(0, 'SALES_DIRECTOR',     '销售总监',         1),
(0, 'SALES_REP',          '业务员',           1),
(0, 'CFO',                '财务总监 CFO',      1),
(0, 'FINANCE_STAFF',      '财务专员',         1),
(0, 'RISK_MANAGER',       '风控经理',         1),
(0, 'HEDGE_TRADER',       '套保员',           1),
(0, 'PROCUREMENT_DIR',    '采购总监',         1),
(0, 'WH_MANAGER',         '仓库经理',         1),
(0, 'WH_STAFF',           '仓管员',           1),
(0, 'CUSTOMER_SERVICE',   '客服',             1),
-- PROCESS 加工
(0, 'PROCESS_OWNER',      '加工厂厂长',       1),
(0, 'PRODUCTION_MGR',     '生产经理',         1),
(0, 'QUALITY_MGR',        '质量经理',         1),
(0, 'EQUIPMENT_MGR',      '设备经理',         1),
(0, 'PLAN_MGR',           '计划经理',         1),
(0, 'OPERATOR',           '操作工',           1),
-- MILL 钢厂
(0, 'MILL_OWNER',         '钢厂厂长',         1),
(0, 'MILL_VP',            '生产副总',         1),
(0, 'STEELMAKING_HEAD',   '炼钢车间主任',     1),
(0, 'ROLLING_HEAD',       '轧钢车间主任',     1),
(0, 'COATING_HEAD',       '镀锌车间主任',     1),
(0, 'QC_DIRECTOR',        '质检主管',         1),
(0, 'ENERGY_MGR',         '能源经理',         1)
ON DUPLICATE KEY UPDATE role_name=VALUES(role_name);

-- ----------------------------- 补充 sys_permission -----------------------------
INSERT INTO sys_permission (perm_code, perm_name, description) VALUES
('metric.read',              '读基础指标',         '销售额/库存吨数等基础指标'),
('finance.profit.read',      '财务利润',           '毛利/净利/吨毛利/挂价毛利'),
('finance.cost.read',        '财务成本',           '成本/采购价'),
('finance.ar.read',          '应收账款',           '应收余额/逾期/DSO'),
('finance.ap.read',          '应付账款',           '应付/DPO'),
('risk.read',                '风险敞口',           '授信/客户风险/产地敞口'),
('hedge.read',               '套保头寸',           '套保净敞口/期货盈亏/库存浮亏'),
('price.listed.read',        '挂牌价',             '挂价/挂价毛利/让利空间'),
('price.cost.read',          '成本价',             '移动加权成本/采购价'),
('customer.full.read',       '客户完整信息',       '手机/银行/合同'),
('customer.list.read',       '客户列表',           '仅客户名/客户级别'),
('quality.full.read',        '质量明细',           '客诉/降级率/缺陷'),
('mes.production.read',      '生产/MES 数据',      '工单/OEE/良率'),
('mes.equipment.read',       '设备数据',           'MTBF/MTTR/故障'),
('inventory.detail.read',    '库存明细',           '批次号/库位/库龄'),
('inventory.summary.read',   '库存汇总',           '总库存吨数/金额'),
('admin.tenant',             '租户管理',           '用户/角色配置'),
('admin.metric',             '指标治理管理',       '指标新增/修改'),
('billing.recharge',         '充值',               '套餐购买'),
('billing.refund',           '退款审批',           '退款操作')
ON DUPLICATE KEY UPDATE perm_name=VALUES(perm_name);
