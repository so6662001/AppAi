# DSL 编译器

将 AI 输出的 DSL JSON 编译为安全可执行的 StarRocks SQL。

## 安装

```bash
cd services/dsl-compiler
pip install -e ".[dev]"
```

## 运行

```bash
export METRICS_DIR=$(pwd)/../../metrics
uvicorn dsl_compiler.app:app --reload --port 8000
```

## 测试

```bash
pytest -v
```

## 调用示例

```bash
curl -X POST http://localhost:8000/v1/dsl/compile \
  -H "Content-Type: application/json" -d '{
    "dsl": {
      "metrics": ["sales_amount", "ton_gross_profit"],
      "dimensions": ["org.region", "material.product_type"],
      "filters": [
        {"field": "origin.origin_group", "op": "=", "value": "沙钢系"}
      ],
      "time": {"preset": "last_week", "grain": "day"},
      "compare": {"mode": "wow"},
      "limit": 100
    },
    "context": {
      "tenant_id": 1,
      "user_id": 10,
      "business_line": "TRADE",
      "scopes": ["sales.read"],
      "visible_org_ids": [100, 101]
    }
  }'
```

返回示例：

```json
{
  "sql": "SELECT ...",
  "params": {"p1": 1, "p2": "2026-05-04", "p3": "2026-05-10", ...},
  "tables_used": ["dws_sales_daily"],
  "metrics_expanded": ["sales_amount", "ton_gross_profit"],
  "est_rows": 7000,
  "warnings": ["compare mode: wow (使用 base/prev 双查询)"],
  "biz_token_estimate": 200
}
```

## 编译流水线

1. **Schema 校验** – jsonschema 拒绝结构非法的 DSL
2. **指标解析** – 通过 name/code/synonyms 查找 MetricDef
3. **业务类型裁剪** – 根据 `business_line` 过滤不适用指标
4. **权限校验** – 检查 `auth_required` 与用户 scopes
5. **派生展开** – `requires_metrics` 递归 ≤ 3 层
6. **时间归一** – `preset` 解析为 `(from, to)` 区间，`grain` 映射 date_trunc
7. **半累积处理** – `semantics=snapshot + grain≠day` 自动包内层日 CTE
8. **WHERE 注入** – 强制 `tenant_id`、行级 org/warehouse 权限
9. **比较模式** – `compare.mode` 生成 UNION ALL 两段查询
10. **加固** – LIMIT 上限、参数化、超时

## 错误码

| 代码 | 说明 |
|------|------|
| `E_DSL_SCHEMA` | DSL 结构非法 |
| `E_METRIC_NOT_FOUND` | 指标 + 同义词均未命中 |
| `E_METRIC_STATUS` | 指标已废弃 |
| `E_NOT_APPLICABLE` | 不适用当前业务类型 |
| `E_PERMISSION` | scope 不足 |
| `E_SEMI_ADDITIVE` | snapshot 类指标跨日 SUM |
| `E_DEP_TOO_DEEP` | 派生指标嵌套超 3 层 |
| `E_COST_EXCEEDED` | 预估扫描行数超限 |
