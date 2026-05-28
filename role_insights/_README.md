# 岗位智能画像 - 诊断规则配置

每个文件 = 一个岗位 (role_code) 的画像配置:
- **primary_kpis**: 用于健康度评分的 5-6 个核心指标 + 权重
- **rules**: 诊断规则列表 (短板/风险/机会/合规), 每条规则触发后:
  - 输出 finding (你怎么了)
  - 输出 impact (会损失什么)
  - 给 actions (一键执行 / 跳钻取 / 问 AI)
  - 扣 score_impact 分
- **routines**: 每日例行检查清单
- **education**: AI 教练知识库索引 (当用户问"我该怎么改" 时引用)

服务 `role-insight-service` 每天 7:30 跑批 + 用户登录时实时查, 把结果写入 `role_insight_snapshot`.
