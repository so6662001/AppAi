package com.steel.billing.service;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.steel.billing.lua.LuaScriptManager;
import com.steel.billing.model.Reservation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
public class ReservationService {

    private final LuaScriptManager lua;
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    public ReservationService(LuaScriptManager lua, JdbcTemplate jdbc) {
        this.lua = lua; this.jdbc = jdbc;
    }

    /** 预扣占用. 返回 reservationId + plan. */
    public Reservation preauth(long tenantId, long userId, String sessionId, String messageId,
                               long estimate, boolean needTimes, boolean allowOverrun) {
        String rid = UUID.randomUUID().toString().replace("-", "");
        String walletKey = "wallet:" + tenantId;
        String resvKey = "resv:" + rid;

        List<Object> ret = lua.exec("preauth",
            List.of(walletKey, resvKey),
            List.of(estimate, needTimes ? 1 : 0, allowOverrun ? 1 : 0,
                System.currentTimeMillis(),
                tenantId, userId, sessionId == null ? "" : sessionId,
                messageId == null ? "" : messageId));

        if (ret == null || ret.isEmpty()) throw new RuntimeException("lua return empty");
        Number ok = (Number) ret.get(0);
        if (ok.intValue() != 1) {
            String code = String.valueOf(ret.get(1));
            throw new BillingException(code, "preauth failed: " + code);
        }
        String planJson = String.valueOf(ret.get(1));
        List<Map<String, Object>> plan;
        try {
            plan = mapper.readValue(planJson, new TypeReference<>() {});
        } catch (Exception e) {
            plan = List.of();
        }

        // 异步写 outbox / reservation 持久化
        try {
            jdbc.update("INSERT INTO usage_reservation (reservation_id, tenant_id, user_id, "
                + "session_id, message_id, estimate_tokens, plan_json, status, expires_at) "
                + "VALUES (?,?,?,?,?,?,?,?, NOW() + INTERVAL 180 SECOND)",
                rid, tenantId, userId, sessionId, messageId, estimate, planJson, "HELD");
        } catch (Exception e) {
            log.warn("persist reservation failed (continuing): {}", e.getMessage());
        }

        return new Reservation(rid, tenantId, userId, sessionId, messageId, estimate, plan);
    }

    /** 实际结算 - 多退少补. */
    public Map<String, Object> settle(long tenantId, String reservationId, long actual,
                                      String modelName, Integer inputTokens, Integer outputTokens,
                                      Integer queryRows, Boolean cacheHit, boolean allowOverrun) {
        String walletKey = "wallet:" + tenantId;
        String resvKey = "resv:" + reservationId;
        List<Object> ret = lua.exec("settle",
            List.of(walletKey, resvKey),
            List.of(actual, System.currentTimeMillis(), allowOverrun ? 1 : 0));

        if (ret == null || ret.isEmpty()) throw new RuntimeException("settle empty");
        Number ok = (Number) ret.get(0);
        if (ok.intValue() != 1) {
            String code = String.valueOf(ret.get(1));
            throw new BillingException(code, "settle failed: " + code);
        }
        long diff = ret.size() > 2 ? ((Number) ret.get(2)).longValue() : 0;

        // 写 usage_record
        try {
            jdbc.update("INSERT INTO usage_record (tenant_id, reservation_id, model_name, "
                + "input_tokens, output_tokens, cache_hit, query_rows, biz_tokens_charged, "
                + "bucket, cost_cny, message_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                tenantId, reservationId, modelName, inputTokens, outputTokens,
                cacheHit != null && cacheHit ? 1 : 0, queryRows,
                actual, "MIX", actual / 1000.0 * 0.4, null);
        } catch (Exception e) {
            log.warn("write usage_record failed: {}", e.getMessage());
        }

        // 写 ledger (扣减)
        try {
            jdbc.update("INSERT INTO billing_ledger (tenant_id, ref_type, ref_id, account, "
                + "direction, amount, unit, balance_after) VALUES (?,?,?,?,?,?,?,?)",
                tenantId, "USAGE", reservationId, "MIXED", "DR", actual, "TOKEN", null);
        } catch (Exception ignored) {}

        return Map.of("status", "SETTLED", "diff", diff, "actual", actual);
    }

    /** 释放预扣 (用户中断 / 定时清扫). */
    public Map<String, Object> release(long tenantId, String reservationId) {
        List<Object> ret = lua.exec("release",
            List.of("wallet:" + tenantId, "resv:" + reservationId),
            List.of(System.currentTimeMillis()));
        if (ret == null || ret.isEmpty()) throw new RuntimeException("release empty");
        Number ok = (Number) ret.get(0);
        if (ok.intValue() != 1) {
            String code = String.valueOf(ret.get(1));
            throw new BillingException(code, "release failed: " + code);
        }
        try {
            jdbc.update("UPDATE usage_reservation SET status='RELEASED' WHERE reservation_id=?",
                reservationId);
        } catch (Exception ignored) {}
        return Map.of("status", "RELEASED");
    }

    /** 退款 / 售后调账. */
    public Map<String, Object> refund(long tenantId, String account, long amount, String refId) {
        List<Object> ret = lua.exec("refund",
            List.of("wallet:" + tenantId),
            List.of(account, amount, System.currentTimeMillis(),
                refId == null ? "" : refId));
        if (ret == null || ret.isEmpty()) throw new RuntimeException("refund empty");
        Number ok = (Number) ret.get(0);
        if (ok.intValue() != 1) {
            String code = String.valueOf(ret.get(1));
            throw new BillingException(code, "refund failed: " + code);
        }
        try {
            jdbc.update("INSERT INTO billing_ledger (tenant_id, ref_type, ref_id, account, "
                + "direction, amount, unit, balance_after) VALUES (?,?,?,?,?,?,?,?)",
                tenantId, "REFUND", refId, account, "CR", amount, "TOKEN", null);
        } catch (Exception ignored) {}
        return Map.of("status", "REFUNDED", "amount", amount);
    }
}
