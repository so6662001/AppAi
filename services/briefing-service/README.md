# briefing-service

AI 经营早报后端：每日生成卡片 + 8 个 `/v1/briefing/*` 接口。

```bash
pip install -e ".[dev]"
export DB_URL='mysql+pymysql://...'
uvicorn briefing.app:app --port 8500
```

接口与 `docs/uniapp/ai-briefing-api.openapi.yaml` 一致。

## 测试

```
PYTHONPATH=src pytest -v   # 3 passed
```
