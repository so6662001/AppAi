# AI 经营早报（Daily Briefing） · uniapp 端设计

## 1. 产品定位

- **打开 App 第一屏**，30 秒看懂"昨天卖了多少 / 库存怎么变 / 哪里有风险 / AI 给我建议什么"
- **会"找你"的看板**：不再被动地"我去查"，而是 AI 推关键指标 + 异常 + 行动建议
- 每条卡片都能**追问**（一键进入聊天页继续问）
- 与"角色 + 业务类型"绑定：钢贸老板、加工厂厂长、钢厂质量经理看到的卡片不一样

## 2. 入口与频次

| 入口 | 时机 |
|------|------|
| **App 首页顶部** | 任何时候打开 App, 始终展示当日早报卡片流 |
| **早 08:00 推送** | 推系统通知 + 站内信, 标题 "今日早报已生成" |
| **风控触发推送** | 严重度=HIGH/CRITICAL 立即推 (例: 套保超限、授信突破) |
| **周一周报** | 周一额外一组"上周复盘"卡片 |

不打扰原则：用户可在"设置→推送"里配置静默时段（如夜间不推）；非 CRITICAL 在静默期延后到 08:00。

## 3. 信息架构

```
首页
 ├─ 顶部: 「AI 经营助手」一行
 │     · 头像 + 「今天看什么？」+ 余额胶囊
 ├─ 早报区:
 │   ┌─ 摘要卡 (1张, KPI 4 选)
 │   ├─ 风险卡 (0~N 张, 命中风控规则才出)
 │   ├─ 建议卡 (0~N 张, advice_engine 输出)
 │   ├─ 洞察卡 (1~3 张, AI 找出来的"异常变化")
 │   ├─ 周报卡 (周一才显示)
 │   └─ "查看全部" → 早报历史页
 ├─ 推荐问题 (按角色定制)
 └─ 浮动「AI 助手」按钮
```

## 4. 卡片库（10 种）

### 4.1 摘要卡（每日一张, 必出）

```
┌─────────────────────────────────────────────────────┐
│  早安, 张总 ☀️                            05-13 周三  │
│  ──────────────────────────────────────────────────  │
│  昨日 销售额 1,820 万元   ▲ 12%  比上周一            │
│  昨日 销售吨数  4,820 吨  ▼ 3.2%                     │
│  昨日 吨毛利    +186 元   ▲ ¥22                      │
│  实时 库存金额 18,450 万元 ▲ 1.4%                    │
│                                                      │
│  [追问 AI] [看完整日报]                              │
└─────────────────────────────────────────────────────┘
```

- 4 个 KPI 按角色个性化（老板：销售/毛利/吨毛利/库存；厂长：产量/OEE/良率/能耗）
- 趋势箭头 + 对比基准（"比上周一" / "比上月同日"）
- 点击 KPI 直接跳"销售额近 30 天趋势"详情页

### 4.2 风险卡（命中规则出现）

```
┌─────────────────────────────────────────────────────┐
│  🚨 高风险                                            │
│  客户【宝某科技】授信使用率 98.6%                    │
│  ──────────────────────────────────────────────────  │
│  授信额度 1,000 万 / 已用 986 万 / 逾期 142 万       │
│  风险评分 0.81 (HIGH)                                │
│                                                      │
│  AI 建议:                                            │
│  · 暂停新订单发货                                    │
│  · 限期 7 天内回款 200 万以上                        │
│  · 联系客户经理 王某                                  │
│                                                      │
│  [一键暂停] [指派客户经理] [查看详情] [追问 AI]      │
└─────────────────────────────────────────────────────┘
```

- 严重度三档：🟡MEDIUM 🔴HIGH 🚨CRITICAL，颜色区分
- 操作按钮可直接调业务系统接口（暂停发货等）
- 用户点击「指派」后写入 `advice_inbox.status=ACTED`

### 4.3 建议卡（advice_engine 输出）

```
┌─────────────────────────────────────────────────────┐
│  💡 建议: 加快出货                                    │
│  ──────────────────────────────────────────────────  │
│  沙钢 Q355B 热卷 当前库存 1,820 吨 (高于均值 23%)    │
│  指数预计下周下行 -1.8%, 挂价 4,180                  │
│  ──────────────────────────────────────────────────  │
│  建议:                                               │
│  · 挂特价 4,150 / 吨, 主动联系 Top10 客户            │
│  · 套保对冲 500 吨 (HC 合约)                         │
│                                                      │
│  [生成特价单] [推送给业务员] [追问 AI]               │
└─────────────────────────────────────────────────────┘
```

### 4.4 洞察卡（AI 自动发现的异常变化）

```
┌─────────────────────────────────────────────────────┐
│  🔍 AI 发现                                          │
│  华东大区 达交率 上周 82.3% ▼ 6.2pp                  │
│  ──────────────────────────────────────────────────  │
│  下钻 Top3 原因:                                     │
│  · 物料 M-203 短缺 (280 件)                          │
│  · 设备 EQ-12 故障 4.2h (5/8)                         │
│  · 客户 C-001 临时改单 92 件                          │
│                                                      │
│  [查看图表] [追问 AI] [指派整改]                     │
└─────────────────────────────────────────────────────┘
```

### 4.5 ABC 周报卡（周一）

```
┌─────────────────────────────────────────────────────┐
│  📊 上周 ABC 健康度                                   │
│  ──────────────────────────────────────────────────  │
│  A 类: 102 个 SKU  销售占比 78% (健康)                │
│  C/D 长尾: 487 个 SKU  占库存 32% (偏高 ⚠️)          │
│  死货金额: 1,820 万元  环比 ▲ 5.2%                   │
│                                                      │
│  [查看死货清单 Top50] [生成清呆方案]                 │
└─────────────────────────────────────────────────────┘
```

### 4.6 预测卡

```
┌─────────────────────────────────────────────────────┐
│  🔮 下周预测                                         │
│  ──────────────────────────────────────────────────  │
│  螺纹钢吨毛利     186 → 142 元/吨  ▼                 │
│  90% 置信区间: [128, 158]                            │
│  模型 30 天 MAPE: 8.2% (可信)                        │
│                                                      │
│  [看预测曲线] [追问归因]                             │
└─────────────────────────────────────────────────────┘
```

### 4.7 资金占用卡（钢贸老板专属）

```
┌─────────────────────────────────────────────────────┐
│  💰 客户资金占用 Top5                                │
│  ──────────────────────────────────────────────────  │
│  1. 客户A   占款 ¥2,180万   IRR 18.2%   👍           │
│  2. 客户B   占款 ¥1,650万   IRR  6.4%   ⚠️           │
│  3. 客户C   占款 ¥1,420万   IRR  9.1%                 │
│  4. 客户D   占款 ¥1,280万   IRR  3.2%   ❗ 重点关注   │
│  5. 客户E   占款   ¥980万   IRR -1.4%   🚨 亏钱      │
│                                                      │
│  [全部客户] [追问 AI]                                │
└─────────────────────────────────────────────────────┘
```

### 4.8 异常卡（OEE / 缺货 / 能耗）

```
┌─────────────────────────────────────────────────────┐
│  ⚠️ 1# 冷轧线 OEE 昨日 64.2%  ▼ 8.1pp                │
│  ──────────────────────────────────────────────────  │
│  · 可用率 78%  (停机 5.3h)                            │
│  · 性能率 89%                                         │
│  · 良品率 92%                                         │
│  · 主因: 入口边裂 1.2h, 换辊 1.8h                     │
│                                                      │
│  [设备详情] [整改单] [追问]                          │
└─────────────────────────────────────────────────────┘
```

### 4.9 推荐问题卡（启发式）

```
┌─────────────────────────────────────────────────────┐
│  你可能想问                                           │
│  ┌───────────────┐ ┌───────────────┐                 │
│  │ 上周吨毛利    │ │ 我的销售排名   │                 │
│  └───────────────┘ └───────────────┘                 │
│  ┌───────────────┐ ┌───────────────┐                 │
│  │ 库龄 1 年以上 │ │ 客户 D 历史   │                 │
│  └───────────────┘ └───────────────┘                 │
└─────────────────────────────────────────────────────┘
```

### 4.10 余额提醒卡（计费）

```
┌─────────────────────────────────────────────────────┐
│  ⚠️ Token 余额不足                                    │
│  当前 12,800 / 套餐 5,000,000                         │
│  本月已用 99.7%, 预计今日内用完                       │
│                                                      │
│  [立即续费] [查看用量]                                │
└─────────────────────────────────────────────────────┘
```

## 5. 角色化卡片配置

| 角色 | 默认卡片组合 |
|------|--------------|
| **钢贸老板 (TRADE)** | 摘要 / 风险 / 资金占用 / 建议(出货+套保) / 预测(指数) / ABC(死货) / 余额 |
| **钢贸业务员** | 我的销售KPI / 我的客户风险 / 我的逾期应收 / 推荐问题 |
| **加工厂厂长 (PROCESS)** | 摘要(产量/OEE) / 异常(产线) / 建议(套料/缺货) / 推荐问题 |
| **加工厂计划员** | 待排程工单 / 原料缺料预警 / 推荐问题 |
| **钢厂厂长 (MILL)** | 摘要(出钢量/能耗) / 异常(OEE/故障) / 质量(降级率) / 建议(补库) |
| **钢厂质检** | 化学/力学合格率 / 客诉 8D / 缺陷 Top |
| **CFO/财务** | 净利 / 应收 / 资金占用 / 风险卡 |

配置存 MySQL 表 `briefing_layout`，租户管理员可调整。

## 6. 数据来源 & 生成时机

```
凌晨 03:00 - 03:30   ETL 完成日常数据入仓
凌晨 04:00           ABC 周度刷新 (周一才跑)
凌晨 04:30           Forecast 模型生成 dws_forecast_daily
凌晨 05:00           Advice / Risk 规则引擎扫描 → 写 advice_inbox
凌晨 05:30 - 06:00   briefing-generator 为每个 (tenant,user) 组装卡片
                       · 拉取个性化模板 briefing_layout
                       · 拉取该用户角色对应的指标
                       · 套用阈值过滤 (变化<3% 不出, 重要变化才出)
                       · 写入 briefing_card
凌晨 07:55           推送服务: 站内信 + 微信/钉钉/uni-push 通知
首页打开             从 briefing_card 拉取展示
```

## 7. 后端数据表（追加）

```sql
-- 早报卡片 (放 MySQL steel_chat)
CREATE TABLE briefing_card (
  card_id        BIGINT       NOT NULL AUTO_INCREMENT,
  tenant_id      BIGINT       NOT NULL,
  user_id        BIGINT       NOT NULL,
  biz_date       DATE         NOT NULL,
  card_type      VARCHAR(16)  NOT NULL,    -- SUMMARY/RISK/ADVICE/INSIGHT/ABC/FORECAST/CAPITAL/ANOMALY/RECOMMEND/BALANCE
  severity       VARCHAR(8),               -- LOW/MEDIUM/HIGH/CRITICAL
  rank_score     DECIMAL(8,4),             -- 排序权重
  title          VARCHAR(128),
  payload_json   JSON,                     -- 数据 + 建议动作
  source_metrics JSON,                     -- 引用指标编号, 给追问用
  ref_inbox_id   BIGINT,                   -- 关联 advice_inbox.inbox_id
  status         VARCHAR(16) DEFAULT 'NEW',-- NEW/READ/ACTED/IGNORED
  expires_at     DATETIME,
  created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (card_id),
  KEY idx_user_date (tenant_id, user_id, biz_date)
) ENGINE=InnoDB;

-- 用户早报布局
CREATE TABLE briefing_layout (
  tenant_id   BIGINT NOT NULL,
  user_id     BIGINT NOT NULL,
  role        VARCHAR(32),
  cards       JSON,             -- ["SUMMARY","RISK","ADVICE",...]
  silence_from TIME, silence_to TIME,
  thresholds  JSON,             -- 关键变化阈值, 如 {"sales_amount":0.03}
  updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (tenant_id, user_id)
) ENGINE=InnoDB;
```

## 8. 接口契约

```
GET  /v1/briefing/today
     ?date=2026-05-13            # 缺省为当日
Resp 200:
{
  "biz_date": "2026-05-13",
  "user": {"id":..., "role":"OWNER", "business_line":"TRADE"},
  "cards": [
    {
      "card_id": 12345,
      "type":  "SUMMARY",
      "severity": "LOW",
      "title":   "早安, 张总",
      "rank_score": 100,
      "payload": {
        "kpis": [
          {"metric":"sales_amount", "value":18200000, "unit":"元",
           "trend":{"dir":"up","delta_pct":0.12,"baseline":"上周一"}},
          {"metric":"sales_tonnage","value":4820,    "unit":"吨", "trend":{"dir":"down","delta_pct":-0.032}},
          {"metric":"ton_gross_profit","value":186,  "unit":"元/吨","trend":{"dir":"up","delta_abs":22}},
          {"metric":"inv_amount","value":184500000,"unit":"元","trend":{"dir":"up","delta_pct":0.014}}
        ]
      },
      "actions":[
        {"label":"追问 AI","type":"chat","dsl":{...}},
        {"label":"看完整日报","type":"navigate","path":"/pages/dashboard/daily"}
      ]
    },
    {
      "card_id": 12346,
      "type":  "RISK",
      "severity": "HIGH",
      "title":   "客户【宝某科技】授信使用率 98.6%",
      "payload": { ... },
      "actions": [
        {"label":"一键暂停","type":"action","handler":"freezeShipment","params":{"customer_id":12345}},
        {"label":"指派客户经理","type":"action","handler":"assignManager"},
        {"label":"查看详情","type":"navigate","path":"/pages/customer/detail?id=12345"},
        {"label":"追问 AI","type":"chat","dsl":{...}}
      ]
    }
  ]
}

POST /v1/briefing/cards/{card_id}/mark-read
POST /v1/briefing/cards/{card_id}/act              # 用户执行了建议动作
POST /v1/briefing/cards/{card_id}/ignore
POST /v1/briefing/cards/{card_id}/feedback         # 👍 / 👎 + 原因
GET  /v1/briefing/layout                            # 拉取个性化布局
PUT  /v1/briefing/layout                            # 更新
GET  /v1/briefing/history?from=...&to=...           # 历史早报
```

## 9. 前端组件（uniapp）

```
pages/ai-briefing/
├─ index.vue                   早报主页
├─ history.vue                 历史
└─ layout-setting.vue          布局自定义

components/briefing/
├─ BriefingHeader.vue          顶部问候 + 日期
├─ SummaryCard.vue             摘要卡 (4 KPI)
├─ RiskCard.vue                风险卡
├─ AdviceCard.vue              建议卡
├─ InsightCard.vue             洞察卡 (含小图)
├─ AbcCard.vue                 ABC 周报卡
├─ ForecastCard.vue            预测卡 (含置信带)
├─ CapitalCard.vue             资金占用 Top5
├─ AnomalyCard.vue             异常卡
├─ RecommendCard.vue           推荐问题胶囊
├─ BalanceCard.vue             余额提醒
└─ CardActions.vue             通用操作按钮组 (chat/action/navigate)
```

每个卡片都接受统一 Props：

```ts
defineProps<{
  cardId: number;
  severity: 'LOW'|'MEDIUM'|'HIGH'|'CRITICAL';
  title: string;
  payload: any;
  actions: Array<{
    label: string;
    type: 'chat' | 'action' | 'navigate';
    dsl?: object;
    handler?: string;
    params?: object;
    path?: string;
  }>;
}>();
```

公共 `CardActions.vue` 处理：
- `type=chat` → 跳到 `/pages/ai/chat?dsl=...` 自动发送追问
- `type=action` → 调对应业务接口
- `type=navigate` → 路由跳转

## 10. 推送规则

### 10.1 通知优先级

| 严重度 | 推送方式 | 是否打扰静默 |
|--------|----------|--------------|
| LOW | 站内信 + 红点 | 否 |
| MEDIUM | 站内信 + 红点 + 系统通知（08:00 集中推） | 否 |
| HIGH | 站内信 + 系统通知 + 微信/钉钉 | 否（延后到 08:00） |
| CRITICAL | 站内信 + 系统通知 + 微信/钉钉 + 电话(可选) | **是** (立即推) |

### 10.2 防打扰

- 每用户每日**普通推送**合并为 1 条「您有 X 条早报更新」
- CRITICAL 单独立即推
- 用户可在设置→推送 配置：开关、静默时段、各严重度的渠道偏好
- 7 天内点击率持续<10%的卡片类型，AI 自动降低排序权重

### 10.3 推送渠道实现

```
通知中心 notification-service
  ├─ in-app:    存 chat_session 一条 system message, 推 WebSocket
  ├─ uni-push:  uni.subscribePush
  ├─ wecom:     企业微信应用通知
  ├─ dingtalk:  钉钉工作通知
  ├─ wechat:    服务号模板消息
  └─ sms/call:  仅 CRITICAL, 第三方网关
```

模板示例（CRITICAL）：

> 🚨 钢铁经营助手  
> 您有 1 条紧急告警  
> 内容：客户【宝某科技】授信已超限 ¥14 万  
> 时间：2026-05-13 09:15  
> [立即查看]

## 11. AI 早报生成 Prompt 模板（核心）

```
你是钢铁行业经营分析助手。基于今天的指标数据, 为 {role} 角色生成早报卡片。
当前用户业务类型: {business_line}, 关注域: {focus_domains}
昨日数据快照:
  - sales_amount: ¥{...}, MoM {...}%, WoW {...}%
  - sales_tonnage: {...} 吨
  - inv_amount: ...
  - 风险触发: {risk_alerts_summary}
  - 行动建议: {advice_inbox_summary}
  - 异常: {anomaly_findings}

请按以下规则生成卡片:
1. 必须包含 1 张 SUMMARY 卡 (最重要 4 个 KPI)
2. 命中风控规则的全部生成 RISK 卡, 严重度承袭
3. advice_inbox 中昨晚生成的 ADVICE 卡选 top 3
4. 异常点 (变化 > {threshold}) 选 1-3 个生成 INSIGHT 卡
5. 周一额外生成 ABC 周报卡
6. 卡片排序: CRITICAL > HIGH > MEDIUM > LOW; 同级按 rank_score
7. 总卡片数 <= 8, 防止信息过载

输出 JSON 严格符合 BriefingCard schema, 不要解释。
```

提示词工程要点：
- **prompt 压缩**：把指标数值用紧凑 JSON 传, 不用自然语言
- **用便宜模型**：早报固定模板化, 用 Qwen2.5-7B 本地跑或 deepseek-v3 API
- **生成可缓存**：相同输入相同输出, 命中 L2 缓存只跑一次

## 12. 性能与成本

- 每个用户一次早报生成约 800 input + 1500 output tokens ≈ ¥0.005
- 1000 个用户每天 ≈ ¥5
- 推送侧 uni-push 免费, 微信/钉钉每条几厘
- 总体每日成本 < ¥30, 完全在收入覆盖范围内

## 13. 度量指标（AI 早报本身要被度量）

| 指标 | 目标 |
|------|------|
| 打开率 (DAU 中查看早报的占比) | > 70% |
| 卡片点击率 | > 40% |
| 建议采纳率 (act / show) | > 15% |
| 反馈 👍 比例 | > 80% |
| 单条早报平均阅读时长 | 30-60s |

写入 `briefing_metrics_daily` 周复盘, 持续优化排序与内容。
