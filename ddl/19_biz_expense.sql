-- =====================================================================
-- 业务费 / 抹零 / 返点 (暗规则建模)
-- 默认关闭, 由租户 ENABLE_BIZ_FEE / ENABLE_ROUNDOFF / ENABLE_KICKBACK 显式打开
-- 所有写入必须留审计痕迹 (operator_id + audited_by)
-- =====================================================================
USE steel_dw;

CREATE TABLE IF NOT EXISTS fact_biz_expense (
  tenant_id        BIGINT       NOT NULL,
  entity_id        BIGINT,
  expense_id       BIGINT       NOT NULL,
  expense_date     DATE         NOT NULL,
  -- 性质
  expense_type     VARCHAR(32)  NOT NULL,
    -- BIZ_FEE        业务费 (客户/业务员私下让利, 进销售费用)
    -- ROUNDOFF       抹零 (整单尾差, 进财务调整)
    -- KICKBACK_OUT   返点-给客户
    -- KICKBACK_IN    返点-从上游/钢厂收
    -- FREIGHT_ADJ    运费补贴
    -- QUALITY_CLAIM  质量索赔
    -- COMPLAINT_DEDUCT 客诉扣
  amount           DECIMAL(20,2) NOT NULL,        -- 正负皆可, 抹零通常为负数
  doc_type         VARCHAR(16),                   -- SALES/PURCHASE/STANDALONE
  doc_no           VARCHAR(64),                   -- 关联销售/采购单号
  customer_id      BIGINT,
  supplier_id      BIGINT,
  rep_id           BIGINT,                        -- 关联销售员 (影响提成扣减)
  material_id      BIGINT,
  reason_code      VARCHAR(32),                   -- LOSE_DEAL/QUALITY_GIVEBACK/SPECIAL_PRICE/...
  remark           VARCHAR(512),
  -- 是否纳入提成基数
  affect_commission TINYINT     DEFAULT 1,
  -- 审计
  operator_id      BIGINT,
  audited_by       BIGINT,
  audited_at       DATETIME,
  status           VARCHAR(16)   DEFAULT 'PENDING',  -- PENDING/APPROVED/REJECTED
  src_update_time  DATETIME
)
PRIMARY KEY (tenant_id, expense_id)
PARTITION BY RANGE (expense_date) (
  START ("2022-01-01") END ("2032-01-01") EVERY (INTERVAL 1 MONTH)
)
DISTRIBUTED BY HASH(expense_id) BUCKETS 8
PROPERTIES("replication_num"="3");

-- 业务费上限规则 (防滥用)
USE steel_governance;

CREATE TABLE IF NOT EXISTS biz_expense_limit (
  tenant_id          BIGINT       NOT NULL,
  expense_type       VARCHAR(32)  NOT NULL,
  scope              VARCHAR(16),                   -- TENANT/ORG/REP/CUSTOMER
  scope_id           BIGINT,
  -- 单据/月度上限 (任一为空=不限)
  per_doc_max_amount   DECIMAL(20,2),
  per_doc_max_pct      DECIMAL(8,5),                 -- 占毛利的比例上限
  per_month_max_amount DECIMAL(20,2),
  approval_required_above DECIMAL(20,2),             -- 超此金额走审批
  approval_role        VARCHAR(32),
  is_active            TINYINT      DEFAULT 1,
  updated_at           DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, expense_type, scope, scope_id)
) ENGINE=InnoDB COMMENT='业务费/抹零等暗规则的上限与审批阈值';

-- 默认规则模板
INSERT INTO biz_expense_limit (tenant_id, expense_type, scope, scope_id,
       per_doc_max_amount, per_doc_max_pct, per_month_max_amount, approval_required_above, approval_role, is_active)
VALUES
  (0, 'BIZ_FEE',  'REP', 0, 5000.00,  0.20,  30000.00,  3000.00, 'SALES_DIRECTOR', 1),
  (0, 'ROUNDOFF', 'REP', 0,  500.00,  0.02,   5000.00,  1000.00, 'FINANCE_MGR',    1),
  (0, 'KICKBACK_OUT','CUSTOMER', 0, 20000.00, 0.30, 100000.00, 10000.00, 'CEO',     1)
ON DUPLICATE KEY UPDATE per_doc_max_amount=VALUES(per_doc_max_amount);
