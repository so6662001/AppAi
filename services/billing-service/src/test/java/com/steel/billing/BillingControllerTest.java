package com.steel.billing;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.steel.billing.lua.LuaScriptManager;
import com.steel.billing.service.WalletService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.RedisHashCommands;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class BillingControllerTest {

    @TestConfiguration
    static class TestConfig {

        @Bean @Primary
        public LuaScriptManager luaScriptManager() {
            // Mock 替换真实 LuaScriptManager, 模拟 Redis EVAL 返回
            LuaScriptManager mock = mock(LuaScriptManager.class);
            doAnswer(inv -> {
                String name = inv.getArgument(0);
                return switch (name) {
                    case "preauth" -> List.of(1L, "[{\"b\":\"SUB\",\"h\":2000}]");
                    case "settle"  -> List.of(1L, "SETTLED", -500L);
                    case "release" -> List.of(1L, "RELEASED");
                    case "refund"  -> List.of(1L, "REFUNDED");
                    default -> List.of(0L, "UNKNOWN");
                };
            }).when(mock).exec(anyString(), anyList(), anyList());
            return mock;
        }

        @Bean @Primary
        public StringRedisTemplate stringRedisTemplate() {
            // 完全 mock 掉 Redis, 让 WalletService 走 DB fallback
            StringRedisTemplate t = mock(StringRedisTemplate.class);
            var hashOps = mock(org.springframework.data.redis.core.HashOperations.class);
            when(t.opsForHash()).thenReturn(hashOps);
            when(hashOps.entries(anyString())).thenReturn(Map.of(
                "token_balance", "100000", "times_balance", "5",
                "sub_quota", "500000", "sub_used", "120000",
                "overrun_limit_cent", "20000", "overrun_used_cent", "0",
                "overrun_price_cent_per_1k", "40", "version", "1"
            ));
            return t;
        }
    }

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;

    @Test
    void wallet_query_returns_balances() throws Exception {
        mvc.perform(get("/billing/wallet/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.tokenBalance", is(100000)))
            .andExpect(jsonPath("$.timesBalance", is(5)))
            .andExpect(jsonPath("$.subQuota", is(500000)))
            .andExpect(jsonPath("$.subPeriodLeft", is(380000)));
    }

    @Test
    void preauth_returns_reservation_with_plan() throws Exception {
        var body = Map.of(
            "tenant_id", 1, "user_id", 10,
            "session_id", "s1", "message_id", "m1",
            "estimate", 2000, "need_times", false, "allow_overrun", false);
        mvc.perform(post("/billing/preauth")
                .contentType("application/json")
                .content(mapper.writeValueAsString(body)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.reservationId", notNullValue()))
            .andExpect(jsonPath("$.estimate", is(2000)))
            .andExpect(jsonPath("$.plan", hasSize(greaterThanOrEqualTo(1))));
    }

    @Test
    void settle_returns_diff() throws Exception {
        var body = Map.of(
            "tenant_id", 1, "reservation_id", "abc123",
            "actual", 1500, "model_name", "deepseek-v3",
            "input_tokens", 800, "output_tokens", 700,
            "query_rows", 200, "cache_hit", false, "allow_overrun", false);
        mvc.perform(post("/billing/settle")
                .contentType("application/json")
                .content(mapper.writeValueAsString(body)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("SETTLED")))
            .andExpect(jsonPath("$.diff", is(-500)));
    }

    @Test
    void release_works() throws Exception {
        mvc.perform(post("/billing/release")
                .contentType("application/json")
                .content("{\"tenant_id\":1,\"reservation_id\":\"abc\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("RELEASED")));
    }

    @Test
    void refund_writes_ledger() throws Exception {
        mvc.perform(post("/billing/refund")
                .contentType("application/json")
                .content("{\"tenant_id\":1,\"account\":\"TOKEN\",\"amount\":10000,\"ref_id\":\"order-1\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("REFUNDED")))
            .andExpect(jsonPath("$.amount", is(10000)));
    }

    @Test
    void recharge_increments_balance_and_logs_ledger() throws Exception {
        mvc.perform(post("/billing/wallet/1/recharge")
                .contentType("application/json")
                .content("{\"account\":\"TOKEN\",\"amount\":50000,\"ref_type\":\"ORDER\",\"ref_id\":\"order-7\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("OK")))
            .andExpect(jsonPath("$.amount", is(50000)));
    }
}
