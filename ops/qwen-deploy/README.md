# 本地 Qwen2.5-7B 部署 (vLLM)

## 环境要求

- GPU: 1×4090 24G / A10 24G (起步)
- CUDA 12.1+
- Python 3.10+

## 部署

```bash
# 1. 拉镜像
docker pull vllm/vllm-openai:latest

# 2. 启动服务 (OpenAI 兼容协议, chat-orchestrator 可直连)
docker run -d --name qwen-vllm \
  --runtime nvidia --gpus all \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  --ipc=host \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-7B-Instruct \
  --served-model-name Qwen2.5-7B-Instruct \
  --gpu-memory-utilization 0.85 \
  --max-model-len 8192 \
  --enable-prefix-caching

# 3. 测试
curl http://localhost:8000/v1/models
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen2.5-7B-Instruct","messages":[{"role":"user","content":"你好"}]}'
```

## 接入 chat-orchestrator

```bash
export LLM_PROVIDER=local
export LLM_LOCAL_URL=http://qwen-vllm:8000/v1
export LLM_MODEL=Qwen2.5-7B-Instruct
export LLM_API_KEY=dummy        # vLLM 不校验
```

## 性能

| 场景 | 吞吐 | 延迟(P95) |
|------|------|-----------|
| 意图分类 (50 token) | 50 QPS | 200ms |
| 总结 (200 token) | 20 QPS | 800ms |
| 长文归因 (2000 token) | 5 QPS | 3.5s |

## 成本对比

| 模型 | 输入 | 输出 | 1 万次问答成本 |
|------|------|------|----------------|
| GPT-4 | $30/M | $60/M | ~¥300 |
| DeepSeek-V3 | ¥1/M | ¥2/M | ~¥0.5 |
| **本地 Qwen2.5-7B** | 电费~¥0.1/小时 | — | **~¥0.05** |
