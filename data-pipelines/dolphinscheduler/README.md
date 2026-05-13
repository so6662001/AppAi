# DolphinScheduler 工作流

## 部署

```bash
# 下载 DolphinScheduler 3.2 standalone
wget https://dlcdn.apache.org/dolphinscheduler/3.2.0/apache-dolphinscheduler-3.2.0-bin.tar.gz
tar -xzf apache-dolphinscheduler-*.tar.gz
cd apache-dolphinscheduler-*
bash bin/dolphinscheduler-daemon.sh start standalone-server
# UI: http://localhost:12345/dolphinscheduler
```

## 导入工作流

1. UI 创建项目 `steel-ai-platform`
2. 工作流定义 → 上传 YAML
3. 上线 → 调度触发

或者用 CLI:
```bash
dolphinscheduler-cli workflow import workflow_daily.yaml --project steel-ai-platform
dolphinscheduler-cli workflow import workflow_weekly.yaml --project steel-ai-platform
```

## 任务清单

| 文件 | 调度 | 任务 |
|------|------|------|
| `workflow_daily.yaml` | 每天 23:30 | 6 个 SeaTunnel 同步 + 库存快照 + 风控扫描 + 建议扫描 + 早报生成 |
| `workflow_weekly.yaml` | 每周一 02:00 | 预测模型全量重训 + ABC 重算 |
