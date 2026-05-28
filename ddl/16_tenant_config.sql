-- =====================================================================
-- 多租户配置中心 (steel_governance)
-- 解决:
--   1) 同一套代码服务"钢贸/加工/钢厂/皮包公司"四种业务模式
--   2) 业务费/抹零等暗规则可按租户开关
--   3) 提成规则租户级可配置, 同时内置一套真实数字默认模板
-- =====================================================================
USE steel_governance;

-- ----------------------------- 租户业务模式 (核心路由表) -----------------------------
-- 决定: 哪些指标可见 / 哪些卡片在早报里 / 哪个提成模板初始化
CREATE TABLE IF NOT EXISTS tenant_profile (
  tenant_id          BIGINT       NOT NULL,
  tenant_name        VARCHAR(128) NOT NULL,
  -- 主营业务模式 (单选, 仅作为推荐默认; 可同时启用多个 sub_business_lines)
  primary_business   VARCHAR(16)  NOT NULL,           -- TRADE/PROCESS/MILL/SHELL
  -- 副业务模式 (多选 JSON, 例如同时有钢贸+加工)
  sub_business_lines JSON,
  -- 公司规模档位, 自动套用预设配置 (人头/数据量/默认 KPI 集)
  size_band          VARCHAR(8)   DEFAULT 'SMB',      -- SMB(10-50) / MID(50-200) / LARGE(200-500)
  headcount          INT,
  -- 主体结构
  is_multi_entity    TINYINT      DEFAULT 0,          -- 0=单主体, 1=多法人
  has_hedge_business TINYINT      DEFAULT 0,          -- 是否有期现结合
  has_processing     TINYINT      DEFAULT 0,          -- 是否有加工业务
  fiscal_year_start  VARCHAR(5)   DEFAULT '01-01',    -- 财年起始 (MM-DD)
  base_currency      VARCHAR(8)   DEFAULT 'CNY',
  status             VARCHAR(16)  DEFAULT 'ACTIVE',
  onboarded_at       DATETIME     DEFAULT CURRENT_TIMESTAMP,
  updated_at         DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id)
) ENGINE=InnoDB COMMENT='租户主档 + 业务模式画像';

-- ----------------------------- 租户特性开关 (Feature Flags) -----------------------------
-- 关键: 暗规则/敏感字段都默认关闭, 由租户管理员在后台显式打开
CREATE TABLE IF NOT EXISTS tenant_feature_flag (
  tenant_id       BIGINT       NOT NULL,
  flag_code       VARCHAR(64)  NOT NULL,            -- ENABLE_BIZ_FEE / ENABLE_ROUNDOFF / ENABLE_HEDGE / ENABLE_INTERCOMPANY / ENABLE_KICKBACK / ...
  enabled         TINYINT      NOT NULL DEFAULT 0,
  scope           VARCHAR(16)  DEFAULT 'TENANT',    -- TENANT/ORG/USER
  scope_id        BIGINT,
  config_json     JSON,                              -- 该特性附加参数
  remark          VARCHAR(512),
  updated_by      BIGINT,
  updated_at      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, flag_code, scope, scope_id)
) ENGINE=InnoDB COMMENT='租户特性开关 - 暗规则统一治理入口';

-- 预置 Feature Flag 字典 (供前端枚举)
CREATE TABLE IF NOT EXISTS feature_flag_catalog (
  flag_code        VARCHAR(64)  NOT NULL,
  category         VARCHAR(32),               -- COMMISSION/HEDGE/EXPENSE/REPORT/RISK
  label            VARCHAR(128) NOT NULL,
  description      VARCHAR(512),
  default_enabled  TINYINT      DEFAULT 0,
  audit_required   TINYINT      DEFAULT 0,    -- 是否需要审计留痕
  PRIMARY KEY (flag_code)
) ENGINE=InnoDB;

INSERT INTO feature_flag_catalog (flag_code, category, label, description, default_enabled, audit_required) VALUES
  ('ENABLE_BIZ_FEE',        'EXPENSE',    '业务费建模',         '允许在销售/采购单上挂"业务费", 进入提成与净利核算', 0, 1),
  ('ENABLE_ROUNDOFF',       'EXPENSE',    '抹零建模',           '允许将整单尾差挂"抹零"科目, 不出现在主表里',         0, 1),
  ('ENABLE_KICKBACK',       'EXPENSE',    '佣金/返点建模',      '允许采购返点 + 客户返利双向台账',                       0, 1),
  ('ENABLE_HEDGE',          'HEDGE',      '期现结合',           '启用锁价/点价订单 + 套保头寸 + 基差/敞口指标',          0, 0),
  ('ENABLE_INTERCOMPANY',   'REPORT',     '多法人合并',         '启用 legal_entity 维 + 关联交易抵消 + 合并报表',         0, 0),
  ('ENABLE_AR_INTEREST',    'COMMISSION', '应收占款扣息',       '提成核算时扣除应收资金成本',                            1, 0),
  ('ENABLE_INV_INTEREST',   'COMMISSION', '库存占款扣息',       '提成核算时扣除库存资金成本',                            1, 0),
  ('ENABLE_PREPAY_INTEREST','COMMISSION', '预付款占款扣息',     '提成核算时扣除预付款资金成本(占用上游应付)',            1, 0),
  ('ENABLE_PROFIT_VOLUME_SEG','COMMISSION','利润/走量客群提成', '区分利润型客户 vs 走量型客户给不同提成系数',           1, 0),
  ('ENABLE_DIRECT_INDIRECT','COMMISSION', '直销/间销区分',      '区分直销与转单/挂单, 给不同提成系数',                  1, 0),
  ('ENABLE_PROCESSING_FEE_COMMISSION','COMMISSION','加工费独立提成','把加工费收入与单纯钢贸毛利分开计提',              0, 0),
  ('ENABLE_SHELL_MODE',     'REPORT',     '皮包公司精简模式',   '不依赖库存, 单单看撮合差价 + 资金回款',                 0, 0)
ON DUPLICATE KEY UPDATE label=VALUES(label), description=VALUES(description);

-- ============================================================
-- 提成规则配置 (核心: 每租户一套, 完全可配置, 内置真实数字默认模板)
-- ============================================================
-- 提成方案 (主档)
CREATE TABLE IF NOT EXISTS commission_scheme (
  tenant_id        BIGINT       NOT NULL,
  scheme_id        BIGINT       NOT NULL,
  scheme_code      VARCHAR(64)  NOT NULL,
  scheme_name      VARCHAR(128) NOT NULL,
  business_line    VARCHAR(16),                 -- TRADE/PROCESS/MILL/SHELL
  effective_from   DATE         NOT NULL,
  effective_to     DATE,
  -- 核心基准: 选什么作为提成"原料"
  base_type        VARCHAR(32)  NOT NULL,
  -- LISTED_GROSS_PROFIT (按挂牌毛利, 最常见钢贸口径)
  -- TON_GROSS_PROFIT   (按吨毛利)
  -- NET_PROFIT         (按净利, 扣完应收/库存利息)
  -- PROCESSING_FEE     (按加工费收入)
  -- REVENUE            (按销售额)
  -- SPREAD             (皮包公司: 撮合差价 × 吨)
  rate_default     DECIMAL(8,5) NOT NULL,       -- 默认提成系数, 例如 0.30 (30% of 毛利)
  -- 利息扣减
  ar_interest_rate     DECIMAL(8,6) DEFAULT 0.000125,   -- 0.0125%/天 ≈ 4.5%/年
  inv_interest_rate    DECIMAL(8,6) DEFAULT 0.000150,   -- 0.015%/天 ≈ 5.5%/年
  prepay_interest_rate DECIMAL(8,6) DEFAULT 0.000125,
  -- 是否启用各项
  use_ar_interest      TINYINT DEFAULT 1,
  use_inv_interest     TINYINT DEFAULT 1,
  use_prepay_interest  TINYINT DEFAULT 1,
  -- 客群差异化
  use_customer_seg     TINYINT DEFAULT 1,        -- 是否启用利润型/走量型客户分群
  -- 直销/间销差异化
  use_direct_indirect  TINYINT DEFAULT 1,
  -- 业务费/抹零是否纳入提成基数
  use_biz_fee_deduct   TINYINT DEFAULT 1,
  use_roundoff_deduct  TINYINT DEFAULT 1,
  -- 月度兜底 / 上限
  min_commission_per_month DECIMAL(20,2),         -- 保底
  max_commission_per_month DECIMAL(20,2),         -- 封顶, NULL=不封顶
  -- 季度奖金/年终调节
  quarter_bonus_pct    DECIMAL(8,5)  DEFAULT 0,   -- 季度毛利达标后额外
  yearly_adjust_pct    DECIMAL(8,5)  DEFAULT 0,
  status               VARCHAR(16)   DEFAULT 'DRAFT',  -- DRAFT/ACTIVE/ARCHIVED
  owner_id             BIGINT,
  remark               VARCHAR(512),
  created_at           DATETIME      DEFAULT CURRENT_TIMESTAMP,
  updated_at           DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, scheme_id),
  UNIQUE KEY uk_code (tenant_id, scheme_code, effective_from)
) ENGINE=InnoDB COMMENT='提成方案主档';

-- 提成规则明细行 (条件 × 系数, 按优先级匹配)
CREATE TABLE IF NOT EXISTS commission_rule_line (
  tenant_id       BIGINT       NOT NULL,
  scheme_id       BIGINT       NOT NULL,
  rule_id         BIGINT       NOT NULL,
  rule_label      VARCHAR(128),               -- 例: 直销+现款+A类客户
  priority        INT          NOT NULL DEFAULT 100,   -- 数字小先匹配
  -- 维度匹配条件 (任一为空=该维度任意值)
  match_sales_mode    VARCHAR(16),   -- DIRECT/INDIRECT/CONSIGN/HEDGE_LOCKED/HEDGE_OPEN
  match_settle_type   VARCHAR(16),   -- CASH/T+7/T+30/T+60/T+90/BANK_ACCEPT/COMMERCIAL_ACCEPT
  match_customer_seg  VARCHAR(16),   -- PROFIT/VOLUME/A/B/C (业务上自定义)
  match_product_type  VARCHAR(32),   -- 板材/型材/管材/不锈/进口/特殊
  match_origin_id     BIGINT,
  match_grade_family  VARCHAR(16),
  match_org_id        BIGINT,
  match_min_margin    DECIMAL(20,4), -- 吨毛利门槛
  match_max_margin    DECIMAL(20,4),
  -- 命中后给的系数
  rate                DECIMAL(8,5) NOT NULL,    -- 这条规则的提成系数 (覆盖 scheme.rate_default)
  rate_unit           VARCHAR(8)    DEFAULT 'PCT',  -- PCT=%, YUAN_PER_TON=元/吨
  is_active           TINYINT       DEFAULT 1,
  remark              VARCHAR(512),
  PRIMARY KEY (tenant_id, scheme_id, rule_id),
  KEY idx_priority (tenant_id, scheme_id, priority, is_active)
) ENGINE=InnoDB COMMENT='提成规则明细 - 按优先级匹配的 IF/ELSE 链';

-- 客户分群 (利润型 / 走量型) - 与 dim_customer 解耦, 由销售经理人工/算法标
CREATE TABLE IF NOT EXISTS customer_segment (
  tenant_id        BIGINT       NOT NULL,
  customer_id      BIGINT       NOT NULL,
  segment          VARCHAR(16)  NOT NULL,         -- PROFIT/VOLUME/STRATEGIC/HEDGE/SHELL
  segment_basis    VARCHAR(32),                   -- MANUAL/AUTO_RFM/AUTO_GP_RATE
  effective_from   DATE         NOT NULL,
  effective_to     DATE,
  ar_credit_factor DECIMAL(8,5) DEFAULT 1.0,      -- 给该客户的额外授信系数
  margin_floor     DECIMAL(20,4),                 -- 该客户吨毛利下限 (低于=红线, 不准接单)
  is_active        TINYINT      DEFAULT 1,
  audited_by       BIGINT,
  audited_at       DATETIME,
  PRIMARY KEY (tenant_id, customer_id, segment, effective_from)
) ENGINE=InnoDB COMMENT='客户分群 - 利润型/走量型/战略客户/套保户/皮包户';

-- 销售员归属 + 直销/间销标记
CREATE TABLE IF NOT EXISTS sales_rep_assignment (
  tenant_id          BIGINT       NOT NULL,
  rep_id             BIGINT       NOT NULL,
  customer_id        BIGINT       NOT NULL,
  effective_from     DATE         NOT NULL,
  effective_to       DATE,
  -- 销售口径
  sales_mode         VARCHAR(16)  DEFAULT 'DIRECT',   -- DIRECT/INDIRECT/TRANSIT(转单)/SHELL
  share_ratio        DECIMAL(8,4) DEFAULT 1.0,        -- 1.0=独享; 0.5=与他人分单
  is_local           TINYINT      DEFAULT 1,          -- 本地销售=1, 异地销售=0
  is_active          TINYINT      DEFAULT 1,
  PRIMARY KEY (tenant_id, rep_id, customer_id, effective_from)
) ENGINE=InnoDB COMMENT='销售员-客户归属表 (含直销/间销/分单比例)';

-- 提成计算结果 (审计用 + 工资条用)
CREATE TABLE IF NOT EXISTS commission_calc_result (
  tenant_id           BIGINT       NOT NULL,
  calc_id             BIGINT       NOT NULL AUTO_INCREMENT,
  period_month        VARCHAR(7)   NOT NULL,         -- 2026-05
  rep_id              BIGINT       NOT NULL,
  rep_name            VARCHAR(128),
  scheme_id           BIGINT       NOT NULL,
  -- 基数明细
  gross_profit_listed DECIMAL(20,2) DEFAULT 0,       -- 挂牌毛利
  gross_profit_ton    DECIMAL(20,4) DEFAULT 0,       -- 吨毛利合计
  revenue_amount      DECIMAL(20,2) DEFAULT 0,
  tonnage             DECIMAL(20,4) DEFAULT 0,
  processing_fee      DECIMAL(20,2) DEFAULT 0,
  -- 扣减项
  ar_interest_amt     DECIMAL(20,2) DEFAULT 0,
  inv_interest_amt    DECIMAL(20,2) DEFAULT 0,
  prepay_interest_amt DECIMAL(20,2) DEFAULT 0,
  biz_fee_amt         DECIMAL(20,2) DEFAULT 0,
  roundoff_amt        DECIMAL(20,2) DEFAULT 0,
  bad_debt_amt        DECIMAL(20,2) DEFAULT 0,
  -- 调整项
  direct_indirect_adj DECIMAL(8,5)  DEFAULT 1.0,     -- 直销1.0 / 间销0.5
  customer_seg_adj    DECIMAL(8,5)  DEFAULT 1.0,
  quarter_bonus_amt   DECIMAL(20,2) DEFAULT 0,
  -- 最终值
  base_amount         DECIMAL(20,2) DEFAULT 0,        -- 基数 (扣完利息+业务费后用于提成的数字)
  rate_effective      DECIMAL(8,5),                   -- 加权命中的最终系数
  commission_calc     DECIMAL(20,2) DEFAULT 0,        -- 计算结果
  commission_floor    DECIMAL(20,2),                  -- 保底兜底
  commission_cap      DECIMAL(20,2),                  -- 封顶
  commission_final    DECIMAL(20,2) DEFAULT 0,        -- 最终
  status              VARCHAR(16)   DEFAULT 'DRAFT',   -- DRAFT/CONFIRMED/PAID/DISPUTED
  calc_detail_json    JSON,                            -- 全量明细 (审计 / 复算)
  audited_by          BIGINT,
  audited_at          DATETIME,
  created_at          DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, calc_id),
  UNIQUE KEY uk_period_rep_scheme (tenant_id, period_month, rep_id, scheme_id),
  KEY idx_rep (tenant_id, rep_id, period_month),
  KEY idx_status (tenant_id, status, period_month)
) ENGINE=InnoDB COMMENT='提成计算审计 - 每月每销售员每方案一行';

-- 提成调整流水 (人工调整审计)
CREATE TABLE IF NOT EXISTS commission_adjustment (
  tenant_id       BIGINT       NOT NULL,
  adj_id          BIGINT       NOT NULL AUTO_INCREMENT,
  calc_id         BIGINT       NOT NULL,
  adj_type        VARCHAR(32),                  -- MANUAL_ADD/MANUAL_DEDUCT/BAD_DEBT_WRITEOFF/COMPLAINT_DEDUCT/SPECIAL_BONUS
  amount          DECIMAL(20,2) NOT NULL,
  reason          VARCHAR(512),
  operator_id     BIGINT,
  created_at      DATETIME      DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, adj_id),
  KEY idx_calc (tenant_id, calc_id)
) ENGINE=InnoDB;

-- ----------------------------- 真实数字默认模板 (装入 4 类业务) -----------------------------
-- 内置 4 套真实数字 scheme 模板, 租户开户时自动选一套
-- 钢贸现货 (TRADE): 按挂牌毛利提成, 利润型客户系数高
INSERT INTO commission_scheme (tenant_id, scheme_id, scheme_code, scheme_name, business_line,
       effective_from, base_type, rate_default,
       ar_interest_rate, inv_interest_rate, prepay_interest_rate,
       use_ar_interest, use_inv_interest, use_prepay_interest,
       use_customer_seg, use_direct_indirect, use_biz_fee_deduct, use_roundoff_deduct,
       min_commission_per_month, max_commission_per_month,
       status, remark)
VALUES
  (0, 1, 'TPL_TRADE_GP30',   '【模板】钢贸-按挂牌毛利30%', 'TRADE',
       '2024-01-01', 'LISTED_GROSS_PROFIT', 0.30000,
       0.000125, 0.000150, 0.000125,
       1, 1, 1,
       1, 1, 1, 1,
       3000.00, NULL,
       'ACTIVE', '钢贸现货: 30%挂牌毛利扣完应收/库存利息后计提'),

  (0, 2, 'TPL_PROCESS_FEE15', '【模板】加工-加工费15% + 钢材毛利25%', 'PROCESS',
       '2024-01-01', 'PROCESSING_FEE', 0.15000,
       0.000125, 0.000150, 0.000125,
       1, 1, 1,
       1, 1, 1, 1,
       3500.00, NULL,
       'ACTIVE', '加工厂: 加工费 15% + 钢材买卖毛利 25%, 分两线计提'),

  (0, 3, 'TPL_MILL_TONNAGE',  '【模板】钢厂-按吨毛利元/吨', 'MILL',
       '2024-01-01', 'TON_GROSS_PROFIT', 50.00000,   -- 50 元/吨
       0.000125, 0.000150, 0.000125,
       1, 1, 0,
       0, 0, 0, 0,
       5000.00, NULL,
       'ACTIVE', '钢厂自销: 每吨提 50 元, 不分客群'),

  (0, 4, 'TPL_SHELL_SPREAD',  '【模板】皮包/纯撮合-按差价50%', 'SHELL',
       '2024-01-01', 'SPREAD', 0.50000,
       0, 0, 0,
       0, 0, 0,
       1, 1, 0, 0,
       1500.00, NULL,
       'ACTIVE', '皮包公司: 不持库存, 撮合差价 50% (买入价对卖出价)')
ON DUPLICATE KEY UPDATE rate_default=VALUES(rate_default);

-- 模板下挂的默认规则行
INSERT INTO commission_rule_line (tenant_id, scheme_id, rule_id, rule_label, priority,
       match_sales_mode, match_settle_type, match_customer_seg, rate, rate_unit, is_active)
VALUES
  -- TRADE: 直销+现款+利润型客户 → 35%; 间销+长账期 → 15%; 走量型 → 25%
  (0, 1, 1, '直销+现款+利润型', 10, 'DIRECT', 'CASH',   'PROFIT', 0.35, 'PCT', 1),
  (0, 1, 2, '直销+T+30+利润型',  20, 'DIRECT', 'T+30',   'PROFIT', 0.32, 'PCT', 1),
  (0, 1, 3, '直销+走量型',       30, 'DIRECT', NULL,     'VOLUME', 0.25, 'PCT', 1),
  (0, 1, 4, '间销/转单',         40, 'INDIRECT', NULL,   NULL,     0.15, 'PCT', 1),
  -- PROCESS: 加工费15%; 钢材买卖按 TRADE 一致
  (0, 2, 1, '加工费收入',        10, NULL,       NULL,     NULL,     0.15, 'PCT', 1),
  (0, 2, 2, '直销+利润型',       20, 'DIRECT',   NULL,     'PROFIT', 0.30, 'PCT', 1),
  -- MILL: 不分客群, 统一吨毛利 50 元
  (0, 3, 1, '统一', 10, NULL, NULL, NULL, 50.00, 'YUAN_PER_TON', 1),
  -- SHELL: 撮合差价 50%, 间销/挂单只给 20%
  (0, 4, 1, '撮合直成',     10, 'DIRECT',   NULL, NULL, 0.50, 'PCT', 1),
  (0, 4, 2, '挂单转单中介', 20, 'TRANSIT',  NULL, NULL, 0.20, 'PCT', 1)
ON DUPLICATE KEY UPDATE rate=VALUES(rate);

-- 演示用: 给 tenant_id=1 (默认演示租户) 选 TRADE 模板
INSERT INTO tenant_profile (tenant_id, tenant_name, primary_business, sub_business_lines,
       size_band, is_multi_entity, has_hedge_business, has_processing)
VALUES (1, '演示·钢贸+加工综合体', 'TRADE',
        JSON_ARRAY('TRADE','PROCESS','HEDGE'),
        'MID', 1, 1, 1)
ON DUPLICATE KEY UPDATE tenant_name=VALUES(tenant_name);
