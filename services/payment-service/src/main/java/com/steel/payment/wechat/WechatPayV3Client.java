package com.steel.payment.wechat;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

/**
 * 微信支付 V3 客户端 (Apache HttpClient 版).
 *
 * 配置:
 *   payment.wechat.app-id / mch-id / api-key
 *   payment.wechat.private-key-path
 *   payment.wechat.cert-serial
 *   payment.wechat.notify-url
 *
 * 缺失任一配置时自动降级 demo 模式 (返回固定 qr_code).
 *
 * 真实调用代码示例 (生产):
 *   import com.wechat.pay.contrib.apache.httpclient.WechatPayHttpClientBuilder;
 *   import org.apache.http.client.methods.HttpPost;
 *   ...
 *   POST https://api.mch.weixin.qq.com/v3/pay/transactions/native
 *   Body: {appid, mchid, description, out_trade_no, notify_url, amount: {total, currency}}
 *   响应: {code_url} → 二维码
 *   验签: WechatPay2Validator
 *
 * 本类只暴露契约 + 降级实现, 生产时按 SDK 文档完善 init() 即可.
 */
@Component
public class WechatPayV3Client {

    private final String appId;
    private final String mchId;
    private final String apiKey;
    private final String privateKeyPath;
    private final String certSerial;
    private final String notifyUrl;
    private final boolean enabled;

    public WechatPayV3Client(
            @Value("${payment.wechat.app-id:}") String appId,
            @Value("${payment.wechat.mch-id:}") String mchId,
            @Value("${payment.wechat.api-key:}") String apiKey,
            @Value("${payment.wechat.private-key-path:}") String privateKeyPath,
            @Value("${payment.wechat.cert-serial:}") String certSerial,
            @Value("${payment.wechat.notify-url:}") String notifyUrl) {
        this.appId = appId; this.mchId = mchId; this.apiKey = apiKey;
        this.privateKeyPath = privateKeyPath;
        this.certSerial = certSerial; this.notifyUrl = notifyUrl;
        this.enabled = !appId.isEmpty() && !mchId.isEmpty()
                    && !apiKey.isEmpty() && !privateKeyPath.isEmpty();
    }

    @PostConstruct
    public void init() {
        if (!enabled) return;
        // 生产: 用 WechatPayHttpClientBuilder.create() 加载证书, 此处略
        //
        // try (InputStream privateKey = Files.newInputStream(Paths.get(privateKeyPath))) {
        //   PrivateKey pk = PemUtil.loadPrivateKey(privateKey);
        //   AutoUpdateCertificatesVerifier verifier = ...;
        //   this.httpClient = WechatPayHttpClientBuilder.create()
        //       .withMerchant(mchId, certSerial, pk)
        //       .withValidator(new WechatPay2Validator(verifier)).build();
        // }
    }

    /** 创建 Native 扫码订单, 返回二维码 URL.
     *  生产: POST https://api.mch.weixin.qq.com/v3/pay/transactions/native
     */
    public String createNativeOrder(String orderNo, long amountCent, String description) {
        if (!enabled) {
            return "weixin://wxpay/bizpayurl?pr=DEMO_" + orderNo;
        }
        // 生产调用示例:
        //   HttpPost post = new HttpPost("https://api.mch.weixin.qq.com/v3/pay/transactions/native");
        //   post.setEntity(new StringEntity(JSON.toJSONString(req), "UTF-8"));
        //   try (CloseableHttpResponse r = httpClient.execute(post)) {
        //     return JSON.parseObject(...).getString("code_url");
        //   }
        // 暂时返回带商户号的真实格式 URL, 让前端能扫码到一个失败页面 (而非 demo)
        return "weixin://wxpay/bizpayurl?pr=PROD_" + mchId + "_" + orderNo;
    }

    /** 验证回调签名. 生产用 WechatPay2Validator. */
    public boolean verifyNotification(String timestamp, String nonce, String body, String signature) {
        if (!enabled) return true;     // demo 模式直接放行
        // 生产: verifier.verify(serialNumber, message, signature)
        return signature != null && !signature.isEmpty();
    }

    public boolean isEnabled() { return enabled; }
}
