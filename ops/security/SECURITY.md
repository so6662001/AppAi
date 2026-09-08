# 安全清单

## SQL 注入防护
- ✅ DSL 编译器强制参数化 (`:p1` → `%(p1)s`)
- ✅ 只允许 SELECT, 表名白名单 (`dim_/dwd_/dws_/ads_`)
- ✅ 行权限自动注入 tenant_id + org_id

## XSS 防护
- ✅ 前端用 v-text 而非 v-html
- ✅ 后端 ResponseEntity 自动 JSON 转义

## 鉴权
- ✅ Gateway JWT 校验 + 白名单
- ✅ 各服务从 X-Tenant-Id/X-User-Id 头读用户 (不可被前端绕过, 由 Gateway 注入)
- ✅ 敏感指标 auth_required 字段 + scopes 校验

## 数据脱敏
- 客户手机号: `138****8888` (列级权限 visibility=MASKED)
- 价格字段: 仅 finance.read 角色可见

## 密钥管理
- 生产用 Vault / K8s Secret + Sealed Secrets
- 禁止把 API Key / 商户证书提交到代码仓库
- `.gitignore` 已排除 .env、*.pem、*.p12

## 依赖漏洞
- GitHub Actions security-scan.yml: 每周 Trivy + Bandit + Dependency Review
- Java: OWASP dependency-check (建议加入 mvn plugin)
- Python: pip-audit (建议加入 CI)

## 审计日志
- `query_audit_log` 保留 ≥ 180 天
- 所有计费操作 (preauth/settle/refund) 写 `billing_ledger`
- 指标变更 metric_def_history 永久保留

## 合规
- 个人信息保护法 (PIPL): 客户数据加密存储, 删除请求 30 日内响应
- GDPR (若涉欧): 数据可导出 + 可遗忘
- 等保 2.0 三级 (建议测评)
