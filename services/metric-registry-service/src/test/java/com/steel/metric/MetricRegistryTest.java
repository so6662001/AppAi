package com.steel.metric;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
import static org.hamcrest.Matchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@ActiveProfiles("test")
class MetricRegistryTest {

    @Autowired MockMvc mvc;

    @Test
    void list_filters_by_domain() throws Exception {
        mvc.perform(get("/metrics?domain=SALES"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.total", greaterThanOrEqualTo(3)))
           .andExpect(jsonPath("$.items[0].metric_code", notNullValue()));
    }

    @Test
    void get_detail_returns_full_fields() throws Exception {
        mvc.perform(get("/metrics/M120"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.metric_code", is("M120")))
           .andExpect(jsonPath("$.sensitivity", is("HIGH")));
    }

    @Test
    void get_unknown_returns_404() throws Exception {
        mvc.perform(get("/metrics/UNKNOWN"))
           .andExpect(status().isNotFound());
    }

    @Test
    void patch_updates_owner() throws Exception {
        mvc.perform(patch("/metrics/M001").contentType("application/json")
                .content("{\"owner\":\"李四\"}"))
           .andExpect(status().isOk());
        mvc.perform(get("/metrics/M001"))
           .andExpect(jsonPath("$.owner", is("李四")));
    }

    @Test
    void impact_returns_risk() throws Exception {
        mvc.perform(get("/metrics/M001/impact"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.risk_level", notNullValue()))
           .andExpect(jsonPath("$.dashboards", is(1)));
    }

    @Test
    void overview_returns_kpi() throws Exception {
        mvc.perform(get("/overview"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.total_metrics", is(3)));
    }

    @Test
    void create_then_get() throws Exception {
        mvc.perform(post("/metrics").contentType("application/json")
                .content("{\"metric_code\":\"M999\",\"name\":\"test_m\",\"name_zh\":\"测试指标\","
                       + "\"domain\":\"SALES\",\"formula\":\"SUM(x)\",\"owner\":\"tester\"}"))
           .andExpect(status().isCreated());
        mvc.perform(get("/metrics/M999"))
           .andExpect(jsonPath("$.name_zh", is("测试指标")));
    }
}
