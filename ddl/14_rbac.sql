-- =====================================================================
-- RBAC: 用户/角色/权限 + 行列权限
-- =====================================================================
USE steel_governance;

CREATE TABLE IF NOT EXISTS sys_user (
  user_id    BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id  BIGINT       NOT NULL,
  username   VARCHAR(64)  NOT NULL,
  display_name VARCHAR(128),
  email      VARCHAR(128),
  phone      VARCHAR(32),
  password_hash VARCHAR(128),
  is_active  TINYINT DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(user_id),
  UNIQUE KEY uk_user (tenant_id, username)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sys_role (
  role_id    BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id  BIGINT       NOT NULL,
  role_code  VARCHAR(32)  NOT NULL,
  role_name  VARCHAR(64),
  is_active  TINYINT DEFAULT 1,
  PRIMARY KEY(role_id),
  UNIQUE KEY uk_role (tenant_id, role_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sys_user_role (
  user_id    BIGINT NOT NULL,
  role_id    BIGINT NOT NULL,
  PRIMARY KEY (user_id, role_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sys_permission (
  perm_id    BIGINT       NOT NULL AUTO_INCREMENT,
  perm_code  VARCHAR(64)  NOT NULL,
  perm_name  VARCHAR(128),
  description VARCHAR(256),
  PRIMARY KEY(perm_id),
  UNIQUE KEY uk_perm (perm_code)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sys_role_permission (
  role_id    BIGINT NOT NULL,
  perm_id    BIGINT NOT NULL,
  PRIMARY KEY (role_id, perm_id)
) ENGINE=InnoDB;

-- 行级权限: 哪些 org_id / warehouse_id 可见
CREATE TABLE IF NOT EXISTS sys_row_acl (
  acl_id     BIGINT       NOT NULL AUTO_INCREMENT,
  user_id    BIGINT       NOT NULL,
  resource   VARCHAR(32),     -- org / warehouse / workcenter
  resource_ids JSON,
  PRIMARY KEY(acl_id),
  KEY idx_user (user_id, resource)
) ENGINE=InnoDB;

-- 列级权限: 哪些敏感字段不可见
CREATE TABLE IF NOT EXISTS sys_col_acl (
  acl_id     BIGINT NOT NULL AUTO_INCREMENT,
  role_id    BIGINT NOT NULL,
  field      VARCHAR(64),     -- cost_amount / gross_profit / customer_irr...
  visibility VARCHAR(16),     -- HIDDEN / MASKED / FULL
  PRIMARY KEY(acl_id),
  KEY idx_role_field (role_id, field)
) ENGINE=InnoDB;

-- 预置权限
INSERT INTO sys_permission (perm_code, perm_name) VALUES
  ('metric.read',    '读指标'),
  ('metric.edit',    '编辑指标'),
  ('finance.read',   '财务数据查看'),
  ('cost.read',      '成本数据查看'),
  ('report.create',  '创建定时报表'),
  ('report.share',   '分享定时报表'),
  ('billing.recharge', '充值'),
  ('billing.refund',   '退款审批'),
  ('admin.tenant',     '租户管理')
ON DUPLICATE KEY UPDATE perm_name=VALUES(perm_name);
