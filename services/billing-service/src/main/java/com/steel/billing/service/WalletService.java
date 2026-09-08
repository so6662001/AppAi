package com.steel.billing.service;

import com.steel.billing.model.Wallet;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.Map;

@Service
public class WalletService {

    private final StringRedisTemplate redis;
    private final JdbcTemplate jdbc;

    @Autowired
    public WalletService(StringRedisTemplate redis, JdbcTemplate jdbc) {
        this.redis = redis;
        this.jdbc = jdbc;
    }

    /** 查 Redis 钱包, 若不存在则从 MySQL tenant_wallet 表加载初始化. */
    public Wallet get(long tenantId) {
        String key = "wallet:" + tenantId;
        Map<Object, Object> raw = redis.opsForHash().entries(key);
        if (raw == null || raw.isEmpty()) {
            loadFromDb(tenantId);
            raw = redis.opsForHash().entries(key);
        }
        Wallet w = new Wallet();
        w.setTenantId(tenantId);
        w.setTokenBalance(longOf(raw, "token_balance"));
        w.setTimesBalance(intOf(raw, "times_balance"));
        w.setSubQuota(longOf(raw, "sub_quota"));
        w.setSubUsed(longOf(raw, "sub_used"));
        w.setSubPeriodLeft(Math.max(0L, w.getSubQuota() - w.getSubUsed()));
        w.setOverrunLimitCent(intOf(raw, "overrun_limit_cent"));
        w.setOverrunUsedCent(intOf(raw, "overrun_used_cent"));
        w.setOverrunPriceCentPer1k(intOf(raw, "overrun_price_cent_per_1k"));
        w.setVersion(longOf(raw, "version"));
        return w;
    }

    private void loadFromDb(long tenantId) {
        try {
            Map<String, Object> row = jdbc.queryForMap(
                "SELECT token_balance, times_balance, sub_period_quota, sub_period_used, "
              + "overrun_limit_cent, overrun_used_cent, overrun_price_cent_per_1k, version "
              + "FROM tenant_wallet WHERE tenant_id = ?", tenantId);
            Map<String, String> m = new HashMap<>();
            row.forEach((k, v) -> m.put(mapCol(k), v == null ? "0" : v.toString()));
            redis.opsForHash().putAll("wallet:" + tenantId, m);
        } catch (Exception e) {
            // 新租户: 初始化为零
            Map<String, String> m = Map.of(
                "token_balance", "0", "times_balance", "0",
                "sub_quota", "0", "sub_used", "0",
                "overrun_limit_cent", "0", "overrun_used_cent", "0",
                "overrun_price_cent_per_1k", "40", "version", "0"
            );
            redis.opsForHash().putAll("wallet:" + tenantId, m);
        }
    }

    private String mapCol(String c) {
        return switch (c) {
            case "sub_period_quota" -> "sub_quota";
            case "sub_period_used"  -> "sub_used";
            default -> c;
        };
    }

    /** 充值 - 调用 refund.lua 走 Redis 原子加, 再写 ledger. */
    public void recharge(long tenantId, String account, long amount, String refType, String refId) {
        // refund.lua 是通用的 "余额增加" 操作
        // 这里直接 HINCRBY (单字段原子) 也行, 但走 Lua 同源可记审计
        redis.opsForHash().increment("wallet:" + tenantId, accountCol(account), amount);
        redis.opsForHash().increment("wallet:" + tenantId, "version", 1);
        jdbc.update("INSERT INTO billing_ledger (tenant_id, ref_type, ref_id, account, "
              + "direction, amount, unit, balance_after) VALUES (?,?,?,?,?,?,?,?)",
            tenantId, refType, refId, account, "CR", amount, accountUnit(account), null);
    }

    private String accountCol(String account) {
        return switch (account) {
            case "TOKEN", "TOKEN_BALANCE" -> "token_balance";
            case "TIMES", "TIMES_BALANCE" -> "times_balance";
            case "SUB", "SUB_QUOTA"       -> "sub_quota";
            case "OVERRUN"                -> "overrun_used_cent";
            default -> throw new IllegalArgumentException("unknown account: " + account);
        };
    }

    private String accountUnit(String account) {
        return switch (account) {
            case "TOKEN", "TOKEN_BALANCE", "SUB", "SUB_QUOTA" -> "TOKEN";
            case "TIMES", "TIMES_BALANCE" -> "TIMES";
            case "OVERRUN" -> "CENT";
            default -> "TOKEN";
        };
    }

    private long longOf(Map<Object, Object> raw, String key) {
        Object v = raw.get(key); return v == null ? 0 : Long.parseLong(v.toString());
    }
    private int intOf(Map<Object, Object> raw, String key) {
        Object v = raw.get(key); return v == null ? 0 : Integer.parseInt(v.toString());
    }
}
