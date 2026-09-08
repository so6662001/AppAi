"""report-scheduler: 定时报表调度器

启动 APScheduler, 周期扫描 scheduled_report 表, 命中后:
  1) 调 dsl-compiler 编译 SQL
  2) 在 StarRocks 执行
  3) 渲染图表/表格/总结
  4) 写 scheduled_report_run + chat_message
  5) 推送到 INAPP/WECOM/DINGTALK/EMAIL/UNI_PUSH 等渠道
  6) 计入 billing
"""
