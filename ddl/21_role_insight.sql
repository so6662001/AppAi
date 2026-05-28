-- =====================================================================
-- 岗位智能画像 + 指标钻取支持
-- 解决:
--   1) 220+ 指标"有了但企业不会用"的问题 → 给每个岗位生成"健康度+短板+行动"画像
--   2) 任意指标只看到总值, 看不到为什么 → 配置可向下钻取路径 + AI 归因
-- =====================================================================
USE steel_governance;

-- ============================================================
-- 1) 岗位定义 (与业务模式 × 岗位 对应)
-- ============================================================
CREATE TABLE IF NOT EXISTS role_profile (
  role_code         VARCHAR(64)  NOT NULL,           -- TRADE_OWNER / TRADE_SALES_REP / PROCESS_MILL_DIR / FINANCE_CTRL / ...
  role_name         VARCHAR(128) NOT NULL,           -- 中文岗位名: 钢贸老板 / 钢贸销售员 / 加工厂厂长 / 财务总监
  business_line     VARCHAR(16),                     -- TRADE/PROCESS/MILL/SHELL/ALL
  level             VARCHAR(16),                     -- C_LEVEL/MANAGER/STAFF
  focus_areas       JSON,                            -- ["sales","capital","risk"] 重点关注域
  primary_kpis      JSON,                            -- 核心 4-6 个 KPI code, 用于画像评分
  weight_json       JSON,                            -- 各 KPI 权重, 加权后得健康度
  description       VARCHAR(512),
  is_active         TINYINT      DEFAULT 1,
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (role_code)
) ENGINE=InnoDB COMMENT='岗位定义 - 决定该岗位的画像维度';

INSERT INTO role_profile (role_code, role_name, business_line, level, focus_areas, primary_kpis, weight_json, description) VALUES
  ('TRADE_OWNER',       '钢贸老板',     'TRADE',  'C_LEVEL',
    JSON_ARRAY('sales','capital','risk','profit'),
    JSON_ARRAY('sales_amount','ton_gross_profit','net_margin','capital_occupation','customer_risk_score','combined_hedge_pnl'),
    JSON_OBJECT('sales_amount',0.15,'ton_gross_profit',0.25,'net_margin',0.20,'capital_occupation',0.15,'customer_risk_score',0.15,'combined_hedge_pnl',0.10),
    '钢贸老板视角: 看全局, 看资金效率, 看风险'),
  ('TRADE_SALES_DIR',   '钢贸销售总监', 'TRADE',  'MANAGER',
    JSON_ARRAY('sales','team','commission'),
    JSON_ARRAY('team_revenue','team_ton_gross_profit','team_active_customer','team_avg_commission','commission_to_gp_ratio'),
    JSON_OBJECT('team_revenue',0.25,'team_ton_gross_profit',0.30,'team_active_customer',0.15,'team_avg_commission',0.15,'commission_to_gp_ratio',0.15),
    '钢贸销售总监: 看团队产出与单兵效率'),
  ('TRADE_SALES_REP',   '钢贸销售员',   'TRADE',  'STAFF',
    JSON_ARRAY('my_sales','my_customer','my_capital'),
    JSON_ARRAY('my_ton_gross_profit','my_active_customers','my_ar_balance','my_aged_ar','my_commission_calc'),
    JSON_OBJECT('my_ton_gross_profit',0.35,'my_active_customers',0.20,'my_ar_balance',0.15,'my_aged_ar',0.15,'my_commission_calc',0.15),
    '销售员: 看自己业绩, AI 教练贴身'),
  ('FINANCE_CTRL',      '财务总监',     'ALL',    'MANAGER',
    JSON_ARRAY('finance','risk','compliance'),
    JSON_ARRAY('current_ratio','debt_to_asset','ccc_days','ar_aging_181_365_amount','biz_fee_to_gp_ratio','intercompany_eliminate_amt'),
    JSON_OBJECT('current_ratio',0.15,'debt_to_asset',0.20,'ccc_days',0.20,'ar_aging_181_365_amount',0.20,'biz_fee_to_gp_ratio',0.15,'intercompany_eliminate_amt',0.10),
    '财务总监: 看流动性, 看负债率, 看合规'),
  ('PROCESS_MILL_DIR',  '加工厂厂长',   'PROCESS','MANAGER',
    JSON_ARRAY('oee','quality','energy','cost'),
    JSON_ARRAY('oee','first_pass_yield','energy_per_ton','processing_cost_per_ton','order_otd'),
    JSON_OBJECT('oee',0.30,'first_pass_yield',0.25,'energy_per_ton',0.15,'processing_cost_per_ton',0.20,'order_otd',0.10),
    '加工厂厂长: 看 OEE, 看良率, 看吨成本'),
  ('TRADE_HEDGE_TRADER','期货交易员',   'TRADE',  'STAFF',
    JSON_ARRAY('hedge','risk'),
    JSON_ARRAY('combined_hedge_pnl','locked_unhedged_tonnage','hedge_margin_used','basis_current','net_exposure_after_hedge'),
    JSON_OBJECT('combined_hedge_pnl',0.30,'locked_unhedged_tonnage',0.25,'hedge_margin_used',0.15,'basis_current',0.10,'net_exposure_after_hedge',0.20),
    '期货部: 看 PnL, 看敞口, 看基差'),
  ('TRADE_WH_MANAGER',  '仓库主管',     'TRADE',  'STAFF',
    JSON_ARRAY('inventory','aging','quality'),
    JSON_ARRAY('inv_amount','inv_turnover_days','aged_inv_pct','damage_loss_pct','count_accuracy'),
    JSON_OBJECT('inv_amount',0.20,'inv_turnover_days',0.30,'aged_inv_pct',0.25,'damage_loss_pct',0.15,'count_accuracy',0.10),
    '仓库主管: 看周转, 看库龄, 看准确率'),
  ('TRADE_SALES_MGR',   '销售部经理',   'TRADE',  'MANAGER',
    JSON_ARRAY('team','customer','revenue','growth'),
    JSON_ARRAY('team_revenue','team_ton_gross_profit','team_active_customer_count','team_avg_commission','team_attrition_risk','team_new_customer_count'),
    JSON_OBJECT('team_revenue',0.20,'team_ton_gross_profit',0.25,'team_active_customer_count',0.15,'team_avg_commission',0.15,'team_attrition_risk',0.15,'team_new_customer_count',0.10),
    '销售部经理: 看小团队 (3-8 人), 关注产出+员工成长+客户结构'),
  ('TRADE_PURCHASING_MGR','采购经理',  'TRADE',  'MANAGER',
    JSON_ARRAY('price','supplier','inventory','payment','quality'),
    JSON_ARRAY('purchase_price_vs_index','top1_supplier_share','dpo_days','iqc_pass_rate','prepay_balance','hedge_match_pct','inv_turnover_days'),
    JSON_OBJECT('purchase_price_vs_index',0.25,'top1_supplier_share',0.15,'dpo_days',0.15,'iqc_pass_rate',0.10,'prepay_balance',0.10,'hedge_match_pct',0.15,'inv_turnover_days',0.10),
    '采购经理: 钢贸利润源头 - 买价/集中度/账期/对冲匹配')
ON DUPLICATE KEY UPDATE role_name=VALUES(role_name), focus_areas=VALUES(focus_areas);

-- ============================================================
-- 2) 行业基准 (用于"你 vs 行业"对比)
-- ============================================================
CREATE TABLE IF NOT EXISTS industry_benchmark (
  business_line     VARCHAR(16)  NOT NULL,
  metric_code       VARCHAR(64)  NOT NULL,
  region            VARCHAR(16)  DEFAULT 'CN_ALL',
  size_band         VARCHAR(16)  DEFAULT 'ALL',     -- SMB/MID/LARGE/ALL
  period_year       VARCHAR(8)   NOT NULL,
  -- 三档基准
  p25_value         DECIMAL(20,4),                  -- 25 分位 (后 25%)
  p50_value         DECIMAL(20,4),                  -- 中位数
  p75_value         DECIMAL(20,4),                  -- 75 分位 (前 25%)
  top10_value       DECIMAL(20,4),                  -- Top10 平均
  direction         VARCHAR(8)   DEFAULT 'HIGHER',  -- HIGHER (越高越好) / LOWER (越低越好)
  source            VARCHAR(128),                   -- 上海钢联 / 钢之家 / Mysteel
  remark            VARCHAR(512),
  PRIMARY KEY (business_line, metric_code, region, size_band, period_year)
) ENGINE=InnoDB COMMENT='行业基准 - 用于岗位画像对标';

INSERT INTO industry_benchmark VALUES
  ('TRADE', 'ton_gross_profit',     'CN_ALL', 'ALL', '2026', 120, 165, 215, 280, 'HIGHER', '上海钢联', '吨毛利元/吨'),
  ('TRADE', 'gross_margin_pct',     'CN_ALL', 'ALL', '2026', 0.06, 0.092, 0.126, 0.182, 'HIGHER', '上海钢联', '毛利率'),
  ('TRADE', 'net_margin_pct',       'CN_ALL', 'ALL', '2026', 0.018, 0.032, 0.052, 0.082, 'HIGHER', '上海钢联', '净利率'),
  ('TRADE', 'ccc_days',             'CN_ALL', 'ALL', '2026', 70, 56, 38, 22, 'LOWER', '上海钢联', '现金循环天'),
  ('TRADE', 'ar_aging_181_365_pct', 'CN_ALL', 'ALL', '2026', 0.12, 0.06, 0.025, 0.008, 'LOWER', '上海钢联', '账龄180+占比'),
  ('TRADE', 'debt_to_asset',        'CN_ALL', 'ALL', '2026', 0.78, 0.65, 0.52, 0.42, 'LOWER', '上海钢联', '资产负债率'),
  ('TRADE', 'inv_turnover_days',    'CN_ALL', 'ALL', '2026', 56, 42, 28, 18, 'LOWER', '上海钢联', '存货周转天'),
  ('TRADE', 'commission_to_gp_ratio','CN_ALL','ALL', '2026', 0.45, 0.32, 0.22, 0.18, 'LOWER', '行业访谈', '提成占毛利比'),
  ('PROCESS', 'oee',                'CN_ALL', 'ALL', '2026', 0.62, 0.74, 0.85, 0.92, 'HIGHER', '工信部', '设备综合效率'),
  ('PROCESS', 'first_pass_yield',   'CN_ALL', 'ALL', '2026', 0.92, 0.96, 0.985, 0.995, 'HIGHER', '工信部', '一次合格率'),
  ('PROCESS', 'energy_per_ton',     'CN_ALL', 'ALL', '2026', 88, 72, 58, 42, 'LOWER', '工信部', '吨钢能耗 kgce/t'),
  ('MILL',   'ton_gross_profit',    'CN_ALL', 'ALL', '2026', 80, 130, 180, 260, 'HIGHER', '钢协', '钢厂吨毛利')
ON DUPLICATE KEY UPDATE p50_value=VALUES(p50_value);

-- ============================================================
-- 3) 岗位短板诊断规则 (Insight Rule)
-- ============================================================
CREATE TABLE IF NOT EXISTS insight_rule (
  rule_id           VARCHAR(64)  NOT NULL,
  role_code         VARCHAR(64)  NOT NULL,
  category          VARCHAR(32),                    -- WEAKNESS/RISK/OPPORTUNITY/COMPLIANCE
  severity          VARCHAR(8)   DEFAULT 'MEDIUM',
  title             VARCHAR(256) NOT NULL,
  -- 触发条件 (DSL-like, 在 role-insight-service 里求值)
  when_expr         VARCHAR(1024),                  -- e.g. "my_aged_ar > 200000 AND my_aged_ar_pct > 0.15"
  -- 建议输出
  finding_tpl       VARCHAR(1024),                  -- "您的 181+ 账龄应收 {my_aged_ar:,.0f} 元, 占总应收 {my_aged_ar_pct:.0%}, 高于同组员均值 {peer_avg:.0%}"
  impact_tpl        VARCHAR(512),                   -- "潜在坏账 ≈ {risk_amount:,.0f}, 占本月预计提成 {ratio:.0%}"
  -- 推荐行动 (JSON 数组, 含 action_handler 可一键执行)
  actions_json      JSON,
  -- 评分 (用于岗位健康度)
  score_impact      INT          DEFAULT 5,        -- 触发后扣分 (满分 100)
  is_active         TINYINT      DEFAULT 1,
  PRIMARY KEY (rule_id)
) ENGINE=InnoDB COMMENT='岗位诊断规则 - YAML 同步存档表';

-- 演示数据: 销售员的 5 条诊断规则
INSERT INTO insight_rule VALUES
  ('TR_REP_TGP_LOW',  'TRADE_SALES_REP', 'WEAKNESS', 'HIGH',
   '吨毛利低于团队均值',
   'my_ton_gross_profit < team_avg_ton_gross_profit * 0.85',
   '您本月吨毛利 {my_ton_gross_profit:.0f} 元/吨, 比团队均值 {team_avg_ton_gross_profit:.0f} 元/吨 低 {gap_pct:.0%}',
   '若达到团队均值, 本月可多挣 {potential:.0f} 元提成',
   JSON_ARRAY(
     JSON_OBJECT('label','看下哪些单拉低均值','type','navigate','path','/drilldown?metric=my_ton_gross_profit&dim=order'),
     JSON_OBJECT('label','AI 帮我分析','type','chat','prompt','为什么我吨毛利低?'),
     JSON_OBJECT('label','学优秀同事玩法','type','navigate','path','/role-insight/peer?top=1')
   ),
   15, 1),

  ('TR_REP_CUST_CONC','TRADE_SALES_REP', 'RISK', 'MEDIUM',
   '客户过于集中',
   'top2_customer_share > 0.70',
   '您前 2 大客户占了 {top2_customer_share:.0%} 的销售额, 客户集中度风险较高',
   '若 Top1 客户停单, 您下月收入预计下降 {potential:.0f} 元',
   JSON_ARRAY(
     JSON_OBJECT('label','AI 推荐潜在新客户','type','chat','prompt','给我推荐 5 个可开发的客户'),
     JSON_OBJECT('label','看客户结构','type','navigate','path','/drilldown?metric=my_revenue&dim=customer')
   ),
   8, 1),

  ('TR_REP_AR_AGED','TRADE_SALES_REP',   'RISK', 'HIGH',
   '老应收偏多',
   'my_aged_ar_pct > 0.15',
   '您 181 天以上账龄应收 {my_aged_ar:,.0f} 元, 占比 {my_aged_ar_pct:.0%}',
   '若按 30% 坏账率, 潜在损失 {risk_amount:,.0f} 元, 直接影响您提成',
   JSON_ARRAY(
     JSON_OBJECT('label','一键发催收','type','action','handler','sendDunningSms'),
     JSON_OBJECT('label','看客户清单','type','navigate','path','/drilldown?metric=my_aged_ar&dim=customer')
   ),
   12, 1),

  ('TR_REP_INDIRECT_HIGH','TRADE_SALES_REP', 'OPPORTUNITY', 'MEDIUM',
   '间销占比偏高 (提成系数被打 5 折)',
   'indirect_share > 0.40',
   '您间销订单占 {indirect_share:.0%}, 提成被打 5 折. 若改为直销, 可多挣 {potential:.0f}',
   '本月预计漏掉提成 {potential:.0f} 元',
   JSON_ARRAY(
     JSON_OBJECT('label','哪些单是间销','type','navigate','path','/drilldown?metric=indirect_share&dim=order'),
     JSON_OBJECT('label','AI 教我谈直销','type','chat','prompt','客户为什么不愿意直签, 怎么改')
   ),
   10, 1),

  ('TR_REP_NO_NEW','TRADE_SALES_REP',    'OPPORTUNITY', 'LOW',
   '本季无新客户',
   'new_customer_count_qtr = 0',
   '您本季度未开发新客户, 客户池在缩小',
   '同组员均开发了 {peer_avg:.0f} 个新客户',
   JSON_ARRAY(
     JSON_OBJECT('label','AI 推荐潜在客户','type','chat','prompt','给我推荐 10 个值得开发的客户')
   ),
   5, 1),

  ('TR_OWNER_HEDGE_GAP','TRADE_OWNER',   'RISK',     'HIGH',
   '锁价单未对冲过多',
   'locked_unhedged_tonnage > 500',
   '已锁价但未对冲 {locked_unhedged_tonnage:.0f} 吨, 单边价格波动 100 元/吨, 直接亏损 {risk_amount:,.0f}',
   '建议立即开期货空头对冲, 保护毛利',
   JSON_ARRAY(
     JSON_OBJECT('label','一键对冲','type','action','handler','autoHedge'),
     JSON_OBJECT('label','看锁价订单清单','type','navigate','path','/hedge-board?filter=unhedged')
   ),
   18, 1),

  ('FIN_CCC_HIGH', 'FINANCE_CTRL',        'WEAKNESS', 'HIGH',
   '现金循环天数高于行业中位数',
   'ccc_days > p50',
   '现金循环 {ccc_days:.0f} 天, 比行业中位 {p50:.0f} 天多 {gap:.0f} 天',
   '相当于多占用资金 {capital_cost:,.0f} 元, 年化利息成本 {interest_cost:,.0f}',
   JSON_ARRAY(
     JSON_OBJECT('label','分解 CCC','type','navigate','path','/drilldown?metric=ccc_days&dim=composition'),
     JSON_OBJECT('label','看应收/库存/应付天数','type','chat','prompt','为什么我们 CCC 比同行慢')
   ),
   12, 1),

  ('FIN_BIZ_FEE_HIGH','FINANCE_CTRL',     'COMPLIANCE','HIGH',
   '业务费占毛利比偏高',
   'biz_fee_to_gp_ratio > 0.10',
   '业务费占毛利 {biz_fee_to_gp_ratio:.0%}, 超出健康线 10%',
   '本月已支出 {biz_fee_amt:,.0f} 元, 重点关注 Top3 销售员',
   JSON_ARRAY(
     JSON_OBJECT('label','看 Top 业务员','type','navigate','path','/biz-expense-audit?orderby=top'),
     JSON_OBJECT('label','下调上限规则','type','navigate','path','/biz-expense-audit/limits')
   ),
   10, 1)
ON DUPLICATE KEY UPDATE title=VALUES(title);

-- ============================================================
-- 4) 钻取路径配置 (告诉 UI 哪个指标能往哪几个维度钻)
-- ============================================================
CREATE TABLE IF NOT EXISTS metric_drilldown_path (
  metric_code       VARCHAR(64)  NOT NULL,
  path_order        INT          NOT NULL,         -- 推荐顺序 (老板看的): 1=首选
  dim_code          VARCHAR(64)  NOT NULL,         -- customer/product_type/origin/grade/region/rep_id/...
  dim_label         VARCHAR(64),                   -- 客户 / 产品类型 / 产地 / 材质 / ...
  visualization     VARCHAR(32)  DEFAULT 'bar',    -- bar/pie/treemap/heatmap
  topn              INT          DEFAULT 10,
  ai_prompt_tpl     VARCHAR(512),                  -- AI 归因提示模板
  PRIMARY KEY (metric_code, path_order)
) ENGINE=InnoDB COMMENT='指标钻取路径 - 决定 UI 推荐钻什么';

INSERT INTO metric_drilldown_path VALUES
  ('sales_amount',      1, 'customer',     '客户',     'bar',     10, '按客户拆: Top {topn} 占比 {topn_share:.0%}, 是否过于集中?'),
  ('sales_amount',      2, 'product_type', '产品类型', 'pie',     10, '按产品: 主营 {top_product} 占 {top_share:.0%}, 结构是否健康?'),
  ('sales_amount',      3, 'origin',       '产地',     'treemap', 10, '按产地: 哪个钢厂系贡献最大'),
  ('sales_amount',      4, 'region',       '区域',     'bar',     10, '按区域: 华东/华北/华南'),
  ('sales_amount',      5, 'rep_id',       '销售员',   'bar',     15, '按销售员: 业绩分布是否均衡'),

  ('ton_gross_profit',  1, 'product_type', '产品类型', 'bar',      8, '哪个产品毛利好/差?'),
  ('ton_gross_profit',  2, 'customer',     '客户',     'bar',     10, 'Top 利润客户; 是否被走量客户拉低?'),
  ('ton_gross_profit',  3, 'origin',       '产地',     'bar',     10, '哪些产地高溢价能力?'),
  ('ton_gross_profit',  4, 'rep_id',       '销售员',   'bar',     15, '哪些销售员高毛利? 学他玩法'),

  ('capital_occupation',1, 'customer',     '客户',     'bar',     15, 'Top 占资金客户 + IRR 评级'),
  ('capital_occupation',2, 'rep_id',       '销售员',   'bar',     15, '哪些销售员占资金过多?'),
  ('capital_occupation',3, 'aging_band',   '账龄段',   'bar',      6, '0-30/31-60/61-90/91-180/180+ 分布'),

  ('inv_amount',        1, 'origin',       '产地',     'treemap', 10, '哪个钢厂系库存最大?'),
  ('inv_amount',        2, 'product_type', '产品',     'bar',     10, '什么产品压货多?'),
  ('inv_amount',        3, 'aging_band',   '库龄',     'bar',      6, '0-30/31-60/61-90/91-180/180+'),
  ('inv_amount',        4, 'warehouse',    '仓库',     'bar',      8, '哪个仓压货多?'),

  ('ar_amount',         1, 'customer',     '客户',     'bar',     15, 'Top 应收客户'),
  ('ar_amount',         2, 'aging_band',   '账龄',     'bar',      6, '账龄分布健康度'),
  ('ar_amount',         3, 'rep_id',       '销售员',   'bar',     15, '哪些销售员应收最多?'),

  ('net_profit',        1, 'entity_id',    '主体',     'bar',      8, '哪个主体最赚/最亏?'),
  ('net_profit',        2, 'product_type', '产品',     'bar',     10, '哪个产品贡献利润?'),
  ('net_profit',        3, 'customer',     '客户',     'bar',     15, '哪些客户贡献利润?'),

  ('biz_fee_total',     1, 'rep_id',       '销售员',   'bar',     15, '业务费 Top 销售员'),
  ('biz_fee_total',     2, 'customer',     '客户',     'bar',     10, '业务费 Top 客户'),
  ('biz_fee_total',     3, 'reason_code',  '事由',     'pie',      8, '业务费用途分布')
ON DUPLICATE KEY UPDATE dim_label=VALUES(dim_label);

-- ============================================================
-- 5) 岗位画像快照 (每天/每登录跑一次, 存结果)
-- ============================================================
CREATE TABLE IF NOT EXISTS role_insight_snapshot (
  tenant_id         BIGINT       NOT NULL,
  snapshot_id       BIGINT       NOT NULL AUTO_INCREMENT,
  user_id           BIGINT       NOT NULL,
  role_code         VARCHAR(64)  NOT NULL,
  snap_date         DATE         NOT NULL,
  -- 总分 + 分项
  health_score      INT,                            -- 0-100
  health_level      VARCHAR(8),                     -- A/B/C/D/E
  trend_vs_last     INT,                            -- 比上次 +x/-x
  -- 评分明细
  score_breakdown   JSON,                           -- {"sales":85, "capital":62, "risk":40, "profit":78}
  -- 指标快照 (用作钻取上下文)
  kpi_values_json   JSON,
  benchmark_json    JSON,                           -- 对应行业基准
  -- 触发的诊断结果 (insight_rule × 现实数据)
  findings_json     JSON,                           -- [{rule_id, severity, title, finding, impact, actions}]
  finding_count     INT          DEFAULT 0,
  high_count        INT          DEFAULT 0,
  -- 自动行动建议 (Top 3)
  top_actions_json  JSON,
  -- 状态
  is_viewed         TINYINT      DEFAULT 0,
  viewed_at         DATETIME,
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, snapshot_id),
  UNIQUE KEY uk_user_date (tenant_id, user_id, snap_date),
  KEY idx_role (tenant_id, role_code, snap_date)
) ENGINE=InnoDB COMMENT='岗位画像快照 - 每天 7:30 跑批 + 用户登录即查';

-- ============================================================
-- 6) 钻取操作日志 (用于优化推荐路径)
-- ============================================================
CREATE TABLE IF NOT EXISTS drilldown_log (
  log_id            BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id         BIGINT       NOT NULL,
  user_id           BIGINT       NOT NULL,
  session_id        VARCHAR(64),
  metric_code       VARCHAR(64),
  drill_path        VARCHAR(512),                   -- "customer>region>rep_id" 多层钻取路径
  filters_json      JSON,                           -- 钻取时附带的过滤
  result_rows       INT,
  ms_cost           INT,
  ai_explained      TINYINT      DEFAULT 0,
  user_satisfied    TINYINT,                        -- 0/1/NULL
  created_at        DATETIME     DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (log_id),
  KEY idx_user (tenant_id, user_id, created_at),
  KEY idx_metric (metric_code, created_at)
) ENGINE=InnoDB COMMENT='钻取行为日志';
