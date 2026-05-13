# payment-service

微信 / 支付宝支付接入。

接口：创建订单 → 拉起支付 → 接收回调 → 通知 billing 充值钱包。

生产环境对接：
- 微信支付 V3 API（需要商户号、API 证书、APP/JSAPI ID）
- 支付宝 OpenSDK
- 回调必须验签 (`Wechatpay-Signature` 或 `sign`)

```bash
mvn test    # 1 passed (端到端流程)
```
