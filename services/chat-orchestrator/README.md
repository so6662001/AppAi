# chat-orchestrator (Python + FastAPI)

把用户自然语言转成结构化报表的端到端编排器。

```
用户问 → 意图识别(规则) → 槽位抽取(时间/维度/比较/TopN) → 指标同义词匹配(最长优先)
   → 构造 DSL → 调 dsl-compiler 编译 SQL → 在 StarRocks 执行
   → 渲染 KPI/Table/Chart blocks → 流式一句话总结 → 下钻建议 → 计费事件
```

## 接口

```
POST /v1/chat/messages   (SSE 流式)
POST /v1/chat/preview    (一次性返回, 调试用)
```

SSE 事件：`status / meta / data / token / drilldown_suggestion / usage / done / error`。

## 启动

```bash
pip install -e ".[dev]"
export METRICS_DIR=/workspace/metrics
export DSL_COMPILER_URL=http://localhost:8000
uvicorn chat_orchestrator.app:app --port 8200
```

## 测试

```bash
PYTHONPATH=src pytest -v
# 15 passed (意图 + DSL 构造 + 渲染)
```

## 调用示例

```bash
curl -N -X POST http://localhost:8200/v1/chat/messages \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: 1" -H "X-User-Id: 10" -H "X-Business-Line: TRADE" \
  -d '{"text": "上周华东大区按产品类型的吨毛利"}'
```

返回类似：

```
event: status
data: {"phase":"parsing"}

event: meta
data: {"messageId":"...","intent":"REPORT","metricsMatched":["吨毛利"],"time":"last_week"}

event: status
data: {"phase":"compiling","dsl":{...}}

event: data
data: {"type":"table","columns":["region","product_type","ton_gross_profit"],"rows":[...]}

event: data
data: {"type":"chart","chart":"bar",...}

event: token
data: "last_week 查询返回 8 条记录, Top1: 华东 ton_gross_profit=186"

event: drilldown_suggestion
data: [{"label":"按客户拆解","dsl":{...}}, ...]

event: usage
data: {"inputTokens":24,"outputTokens":18,"queryRows":8,"bizTokensCharged":200}

event: done
data: {"messageId":"..."}
```

## 接入 LLM (可选)

当前实现纯规则 NLU，足以演示与覆盖 80% 经营查询场景。要接入真 LLM：
- 在 `intent.py` 增加 `llm_fallback(text)`：当规则未命中任何指标时调 DeepSeek/Qwen
- 在 `renderer.py` 增加 `summarize_with_llm(rows, dsl)`：用便宜模型生成更自然的中文总结
- 设置 `LLM_PROVIDER=deepseek` `LLM_API_KEY=...`

## 性能与成本

- 规则路径单次响应 < 50ms（不含 SQL 执行）
- 同义词加载启动时一次，常驻内存
- LLM 路径建议只用于"复杂归因"场景，意图分类不需要 LLM
