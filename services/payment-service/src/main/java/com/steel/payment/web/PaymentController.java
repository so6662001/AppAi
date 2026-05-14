package com.steel.payment.web;

import com.steel.payment.wechat.WechatPayV3Client;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 支付服务核心:
 *   POST /payment/orders           创建订单 (套餐选购 → 拉起支付)
 *   POST /payment/orders/{id}/pay  发起支付 (返回 qr_code / pay_url)
 *   POST /payment/notify/wechat    微信支付回调 (通知)
 *   POST /payment/notify/alipay    支付宝支付回调
 *   GET  /payment/orders/{id}      查订单
 *
 * 生产: 接入微信 V3 / 支付宝 OpenSDK; 当前给出占位实现 + 业务流转能跑通.
 */
@RestController
@RequestMapping("/payment")
public class PaymentController {

    private final JdbcTemplate jdbc;
    private final WechatPayV3Client wechat;

    @Autowired
    public PaymentController(JdbcTemplate jdbc, WechatPayV3Client wechat) {
        this.jdbc = jdbc;
        this.wechat = wechat;
    }

    @PostMapping("/orders")
    public ResponseEntity<Map<String, Object>> createOrder(@RequestBody Map<String, Object> body) {
        String orderNo = "P" + System.currentTimeMillis() + UUID.randomUUID().toString().substring(0, 8);
        long tenantId = ((Number) body.get("tenant_id")).longValue();
        long planId = ((Number) body.get("plan_id")).longValue();
        double payAmount = ((Number) body.getOrDefault("pay_amount", 0)).doubleValue();
        String channel = (String) body.getOrDefault("pay_channel", "WECHAT");

        jdbc.update(
            "INSERT INTO billing_order (order_no, tenant_id, plan_id, pay_amount, pay_status, "
          + "pay_channel) VALUES (?,?,?,?,?,?)",
            orderNo, tenantId, planId, payAmount, "PENDING", channel);

        long orderId = jdbc.queryForObject(
            "SELECT order_id FROM billing_order WHERE order_no=?", Long.class, orderNo);

        return ResponseEntity.status(201).body(Map.of(
            "order_id", orderId, "order_no", orderNo,
            "pay_status", "PENDING", "channel", channel));
    }

    @PostMapping("/orders/{id}/pay")
    public Map<String, Object> initiatePay(@PathVariable long id) {
        Map<String, Object> order = jdbc.queryForMap(
            "SELECT * FROM billing_order WHERE order_id=?", id);
        String channel = (String) order.get("pay_channel");
        String orderNo = (String) order.get("order_no");
        double amount = ((Number) order.get("pay_amount")).doubleValue();

        String qrCode;
        if ("WECHAT".equalsIgnoreCase(channel) && wechat.isEnabled()) {
            // 真实微信 V3 调用
            try {
                qrCode = wechat.createNativeOrder(orderNo,
                    Math.round(amount * 100), "钢铁 AI 经营分析平台 #" + id);
            } catch (Exception e) {
                qrCode = "weixin://wxpay/bizpayurl?pr=ERR_" + e.getMessage().substring(0, Math.min(20, e.getMessage().length()));
            }
        } else {
            // 降级 demo
            qrCode = "weixin://wxpay/bizpayurl?pr=DEMO_" + id;
        }
        return Map.of(
            "order_id", id, "channel", channel,
            "qr_code", qrCode, "expire_in_seconds", 600,
            "real_payment", wechat.isEnabled()
        );
    }

    /** 支付回调 - 标准化处理 (真实环境需验签). */
    @PostMapping("/notify/{channel}")
    public Map<String, Object> notify(@PathVariable String channel,
                                      @RequestBody Map<String, Object> body) {
        String orderNo = (String) body.get("order_no");
        String status = (String) body.getOrDefault("status", "PAID");
        if (!"PAID".equals(status)) {
            jdbc.update("UPDATE billing_order SET pay_status=? WHERE order_no=?",
                        status, orderNo);
            return Map.of("status", "ok");
        }
        // 标记已支付
        jdbc.update(
            "UPDATE billing_order SET pay_status='PAID', paid_at=NOW(), pay_trade_no=? WHERE order_no=?",
            body.get("trade_no"), orderNo);

        // TODO: 调 billing-service /wallet/{tid}/recharge 实际充值
        // 这里只更新订单, 由 billing-outbox 异步消费回写钱包

        return Map.of("status", "ok", "order_no", orderNo);
    }

    @GetMapping("/orders/{id}")
    public Map<String, Object> getOrder(@PathVariable long id) {
        return jdbc.queryForMap("SELECT * FROM billing_order WHERE order_id=?", id);
    }
}
