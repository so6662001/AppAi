package com.steel.billing.web;

import com.steel.billing.model.Reservation;
import com.steel.billing.model.Wallet;
import com.steel.billing.service.BillingException;
import com.steel.billing.service.ReservationService;
import com.steel.billing.service.WalletService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/billing")
public class BillingController {

    private final WalletService walletSvc;
    private final ReservationService resvSvc;

    @Autowired
    public BillingController(WalletService walletSvc, ReservationService resvSvc) {
        this.walletSvc = walletSvc; this.resvSvc = resvSvc;
    }

    @GetMapping("/wallet/{tenantId}")
    public Wallet wallet(@PathVariable long tenantId) {
        return walletSvc.get(tenantId);
    }

    @PostMapping("/wallet/{tenantId}/recharge")
    public Map<String, Object> recharge(@PathVariable long tenantId,
                                        @RequestBody Map<String, Object> body) {
        String account = (String) body.getOrDefault("account", "TOKEN");
        long amount = ((Number) body.getOrDefault("amount", 0)).longValue();
        String refType = (String) body.getOrDefault("ref_type", "MANUAL");
        String refId = String.valueOf(body.getOrDefault("ref_id", ""));
        walletSvc.recharge(tenantId, account, amount, refType, refId);
        return Map.of("status", "OK", "amount", amount, "account", account);
    }

    @PostMapping("/preauth")
    public ResponseEntity<?> preauth(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.get("tenant_id")).longValue();
        long uid = ((Number) body.get("user_id")).longValue();
        long estimate = ((Number) body.get("estimate")).longValue();
        try {
            Reservation r = resvSvc.preauth(
                tid, uid,
                (String) body.get("session_id"),
                (String) body.get("message_id"),
                estimate,
                (Boolean) body.getOrDefault("need_times", false),
                (Boolean) body.getOrDefault("allow_overrun", false));
            return ResponseEntity.ok(r);
        } catch (BillingException e) {
            Map<String, Object> err = new HashMap<>();
            err.put("code", e.getCode()); err.put("message", e.getMessage());
            return ResponseEntity.status(HttpStatus.PAYMENT_REQUIRED).body(err);
        }
    }

    @PostMapping("/settle")
    public Map<String, Object> settle(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.get("tenant_id")).longValue();
        return resvSvc.settle(
            tid,
            (String) body.get("reservation_id"),
            ((Number) body.get("actual")).longValue(),
            (String) body.get("model_name"),
            (Integer) body.get("input_tokens"),
            (Integer) body.get("output_tokens"),
            (Integer) body.get("query_rows"),
            (Boolean) body.get("cache_hit"),
            (Boolean) body.getOrDefault("allow_overrun", false));
    }

    @PostMapping("/release")
    public Map<String, Object> release(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.get("tenant_id")).longValue();
        return resvSvc.release(tid, (String) body.get("reservation_id"));
    }

    @PostMapping("/refund")
    public Map<String, Object> refund(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.get("tenant_id")).longValue();
        return resvSvc.refund(
            tid,
            (String) body.get("account"),
            ((Number) body.get("amount")).longValue(),
            (String) body.get("ref_id"));
    }
}
