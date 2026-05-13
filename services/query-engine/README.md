# query-engine

统一查询服务: chat-orchestrator / report-scheduler / advice-engine 都通过它执行 SQL。

- L1 缓存: SQL+参数哈希 → Redis 5min TTL
- 审计: 异步写 `query_audit_log`
- 行限制: 默认 50k, 防爆内存

```bash
pip install -e ".[dev]"
uvicorn query_engine.app:app --port 8800
PYTHONPATH=src pytest -v    # 5 passed
```
