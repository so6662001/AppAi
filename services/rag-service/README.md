# rag-service

- 启动时离线 embed 全部 metrics/*.yaml 指标(label/synonyms/notes)
- `POST /v1/rag/search` 返回 Top-K 最相关指标
- `GET /v1/router?task=...` 多模型路由决策

生产建议：
- 嵌入模型换 bge-m3 / OpenAI text-embedding-3-small
- 向量库换 Milvus / pgvector

```bash
PYTHONPATH=src pytest -v   # 6 passed
```
