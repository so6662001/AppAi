package com.steel.metric;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import java.util.List;
import java.util.Map;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class MetricPackTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;

    @Test
    void list_packs_by_business_line() throws Exception {
        mvc.perform(get("/metric-packs?business_line=TRADE"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.total", greaterThanOrEqualTo(3)))
           .andExpect(jsonPath("$.items[0].pack_id", notNullValue()));
    }

    @Test
    void get_pack_detail() throws Exception {
        mvc.perform(get("/metric-packs/PK_TRADE_OWNER"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.role_code", is("OWNER")))
           .andExpect(jsonPath("$.metric_count", is(178)));
    }

    @Test
    void recommend_pack_by_role() throws Exception {
        mvc.perform(get("/metric-packs/recommend?biz=TRADE&role=SALES_REP"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.primary.pack_id", is("PK_TRADE_SALES_REP")));
    }

    @Test
    void save_user_preferences_via_onboarding() throws Exception {
        var body = Map.of(
            "business_line", "TRADE",
            "primary_role", "SALES_REP",
            "interests", List.of("销售", "客户", "应收")
        );
        mvc.perform(put("/user/preferences")
                .header("X-User-Id", "100").header("X-Tenant-Id", "1")
                .contentType("application/json")
                .content(mapper.writeValueAsString(body)))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.status", is("OK")))
           .andExpect(jsonPath("$.onboarding_done", is(true)));

        mvc.perform(get("/user/preferences")
                .header("X-User-Id", "100"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.primary_role", is("SALES_REP")));
    }

    @Test
    void visible_metrics_after_onboarding() throws Exception {
        // 先 onboarding
        var body = Map.of("business_line", "TRADE", "primary_role", "SALES_REP",
                          "interests", List.of());
        mvc.perform(put("/user/preferences").header("X-User-Id", "101")
                .contentType("application/json").content(mapper.writeValueAsString(body)));

        mvc.perform(get("/user/visible-metrics").header("X-User-Id", "101"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.primary_role", is("SALES_REP")))
           .andExpect(jsonPath("$.metrics", hasItem("sales_amount")));
    }

    @Test
    void add_metric_to_watch_list() throws Exception {
        // 先 onboarding
        mvc.perform(put("/user/preferences").header("X-User-Id", "102")
                .contentType("application/json")
                .content("{\"primary_role\":\"SALES_REP\",\"interests\":[]}"));

        mvc.perform(post("/user/watch")
                .header("X-User-Id", "102")
                .contentType("application/json")
                .content("{\"metric_code\":\"customer_irr\"}"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.status", is("OK")));

        mvc.perform(get("/user/visible-metrics").header("X-User-Id", "102"))
           .andExpect(jsonPath("$.metrics", hasItem("customer_irr")));
    }

    @Test
    void subscribe_extra_pack() throws Exception {
        mvc.perform(put("/user/preferences").header("X-User-Id", "103")
                .contentType("application/json")
                .content("{\"primary_role\":\"SALES_REP\",\"interests\":[]}"));

        mvc.perform(post("/metric-packs/PK_TRADE_CFO/subscribe")
                .header("X-User-Id", "103"))
           .andExpect(status().isCreated())
           .andExpect(jsonPath("$.status", is("subscribed")));
    }

    @Test
    void apply_and_approve_metric_permission() throws Exception {
        // 用户申请
        var apply = mvc.perform(post("/metric-apply")
                .header("X-User-Id", "104").header("X-Tenant-Id", "1")
                .contentType("application/json")
                .content("{\"metric_code\":\"net_profit\",\"scope_code\":\"finance.profit.read\","
                       + "\"reason\":\"我需要看净利润\",\"duration_days\":30}"))
           .andExpect(status().isCreated())
           .andReturn();

        // Owner 查看 pending
        mvc.perform(get("/metric-apply/pending").header("X-Tenant-Id", "1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].metric_code", is("net_profit")));

        // 批准
        long applyId = 1L;
        mvc.perform(post("/metric-apply/" + applyId + "/approve")
                .header("X-User-Id", "1")
                .contentType("application/json")
                .content("{\"comment\":\"ok\"}"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.status", is("APPROVED")));

        // 用户查自己的申请
        mvc.perform(get("/metric-apply/my").header("X-User-Id", "104"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].status", is("APPROVED")));
    }
}
