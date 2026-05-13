# K8s / Helm 部署

## 前置
- K8s 1.25+
- Helm 3.10+
- cert-manager (HTTPS)
- 内网 Harbor (推送 17 个服务镜像)

## 部署

```bash
# 1. 创建 namespace + Secrets
kubectl create namespace steel-ai
kubectl create secret generic db-secret -n steel-ai \
  --from-literal=url="jdbc:mysql://mysql:3306/steel_chat" \
  --from-literal=user=root \
  --from-literal=password='STRONG-PWD'

# 2. 安装
helm install steel-ai ./helm/steel-ai \
  -n steel-ai \
  -f ./helm/steel-ai/values-prod.yaml

# 3. 升级
helm upgrade steel-ai ./helm/steel-ai -n steel-ai

# 4. 卸载
helm uninstall steel-ai -n steel-ai
```

模板会按 `values.yaml` 的 `services` 字段生成 17 个 Deployment + Service + HPA。
