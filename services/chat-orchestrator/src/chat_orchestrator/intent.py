"""意图识别 + 槽位抽取 (规则版, 不依赖外部 LLM)。

意图分 4 类:
  - REPORT : 报表(KPI/明细/趋势)
  - DRILL  : 下钻归因
  - DETAIL : 明细查询
  - CHAT   : 闲聊/无法识别

槽位:
  - time   : { preset: yesterday|last_week|last_month|... }
  - dims   : [org.region, material.product_type, customer, ...]
  - filters: [{field, op, value}]
  - compare: yoy/mom/wow
  - metrics: 通过 _match_metrics() 从 metric registry 找
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


# ============ 时间词 ============
_TIME_KEYWORDS = [
    (r"今天|本日", "today"),
    (r"昨天|昨日", "yesterday"),
    (r"本周|这周|这个礼拜", "this_week"),
    (r"上周|上礼拜", "last_week"),
    (r"本月|这个月", "mtd"),
    (r"上月|上个月", "last_month"),
    (r"本季度", "qtd"),
    (r"今年|本年|年初至今|YTD", "ytd"),
    (r"最近?7天|近7日|最近一周", "rolling_7d"),
    (r"最近?30天|近30日|最近一个月", "rolling_30d"),
    (r"最近?90天|近90日|最近三个月", "rolling_90d"),
]

_COMPARE_KEYWORDS = [
    (r"同比|去年同期", "yoy"),
    (r"环比.*月|比上月", "mom"),
    (r"环比.*周|比上周|周环比", "wow"),
    (r"日环比|比昨天", "dod"),
]

# ============ 维度词 ============
_DIM_KEYWORDS = [
    (r"按客户|每个客户|客户维度|客户拆", "customer"),
    (r"按产地|按钢厂|产地拆|产地维度", "origin.origin_name"),
    (r"按材质|按钢种|材质拆", "grade"),
    (r"按大区|按区域|按地区", "org.region"),
    (r"按产品|按品种|按品类|按产品类型", "material.product_type"),
    (r"按业务员|按销售|每个业务员", "sales_owner"),
    (r"按仓库|按库房", "warehouse"),
    (r"按工作中心|按产线|按车间", "workcenter"),
    (r"按供应商", "supplier"),
    (r"按月|每月", "date.date_key"),     # 配合 grain=month
]

# ============ 排序词 ============
_ORDER_KEYWORDS = [
    (r"Top\s*(\d+)|前(\d+)名|最高(\d+)", "top"),
    (r"倒数|最差|最低", "bottom"),
]


@dataclass
class Intent:
    type: str = "REPORT"
    metrics_keywords: list[str] = field(default_factory=list)   # 命中的同义词
    time_preset: Optional[str] = None
    grain: str = "day"
    dimensions: list[str] = field(default_factory=list)
    filters: list[dict] = field(default_factory=list)
    compare: Optional[str] = None
    top_n: Optional[int] = None
    order_dir: str = "desc"
    raw_text: str = ""


def detect(text: str, registry_synonyms: list[str]) -> Intent:
    """从自然语言抽出意图/槽位.

    registry_synonyms: 所有指标的 name+label+synonyms 扁平列表, 用于匹配.
    """
    t = (text or "").strip()
    intent = Intent(raw_text=t)

    # 意图分类
    if any(w in t for w in ["为什么", "原因", "归因", "拆解", "怎么了"]):
        intent.type = "DRILL"
    elif any(w in t for w in ["明细", "清单", "列表", "每一条", "每个"]):
        intent.type = "DETAIL"

    # 时间
    for pat, preset in _TIME_KEYWORDS:
        if re.search(pat, t):
            intent.time_preset = preset
            break
    if not intent.time_preset:
        intent.time_preset = "yesterday"      # 默认昨日

    if "按月" in t or "每月" in t: intent.grain = "month"
    if "按周" in t or "每周" in t: intent.grain = "week"

    # 比较
    for pat, mode in _COMPARE_KEYWORDS:
        if re.search(pat, t):
            intent.compare = mode
            break

    # 维度
    for pat, dim in _DIM_KEYWORDS:
        if re.search(pat, t) and dim not in intent.dimensions:
            intent.dimensions.append(dim)

    # Top N
    m = re.search(r"Top\s*(\d+)|前(\d+)|最高的?\s*(\d+)|最低的?\s*(\d+)", t)
    if m:
        intent.top_n = int(next(g for g in m.groups() if g))
        if "倒数" in t or "最差" in t or "最低" in t:
            intent.order_dir = "asc"

    # 指标关键词匹配 - 最长匹配优先, 避免 "吨毛利" 同时命中 "毛利"
    # 思路: 按长度倒序遍历同义词, 命中后在原文标记位置(替换为占位), 短词无法再命中
    sorted_syns = sorted(filter(None, registry_synonyms), key=lambda s: -len(s))
    consumed = list(t)
    seen: set[str] = set()
    for syn in sorted_syns:
        joined = "".join(consumed)
        idx = joined.find(syn)
        if idx >= 0 and syn not in seen:
            seen.add(syn)
            intent.metrics_keywords.append(syn)
            for i in range(idx, idx + len(syn)):
                consumed[i] = "\x00"

    return intent
