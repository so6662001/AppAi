# data-quality-monitor

四类指标质量检查：

| 检查 | 含义 |
|------|------|
| FRESHNESS | 数据最后更新时间是否 ≤ SLA |
| NULL_RATIO | 关键字段空值比例 |
| SPIKE | 相对基线波动 > 阈值 |
| CONSISTENCY | 跨表交叉校验 (parent vs child sum) |

```bash
PYTHONPATH=src pytest -v   # 7 passed
```
