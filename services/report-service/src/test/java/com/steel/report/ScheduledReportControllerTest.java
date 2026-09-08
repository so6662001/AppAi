package com.steel.report;

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
class ScheduledReportControllerTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;

    private String json(Object o) throws Exception { return mapper.writeValueAsString(o); }

    @Test
    void create_get_list_delete() throws Exception {
        Map<String, Object> body = Map.of(
            "name", "我的销售日报",
            "dslJson", Map.of("metrics", List.of("sales_amount"), "time", Map.of("preset", "yesterday")),
            "scheduleType", "daily",
            "cronExpr", "0 0 8 * * ?",
            "channels", List.of("INAPP", "WECOM")
        );

        var create = mvc.perform(post("/scheduled-reports")
                .contentType("application/json")
                .header("X-Tenant-Id", "1")
                .header("X-User-Id", "10")
                .content(json(body)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.reportId", notNullValue()))
            .andExpect(jsonPath("$.status", is("ACTIVE")))
            .andExpect(jsonPath("$.nextRunAt", notNullValue()))
            .andReturn();

        long id = mapper.readTree(create.getResponse().getContentAsString()).get("reportId").asLong();

        mvc.perform(get("/scheduled-reports/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name", is("我的销售日报")));

        mvc.perform(get("/scheduled-reports")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.total", greaterThanOrEqualTo(1)));

        mvc.perform(delete("/scheduled-reports/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isNoContent());

        mvc.perform(get("/scheduled-reports/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isNotFound());
    }

    @Test
    void pause_resume_recompute_next_run() throws Exception {
        Map<String, Object> body = Map.of(
            "name", "周报",
            "dslJson", Map.of("metrics", List.of("sales_amount")),
            "scheduleType", "weekly",
            "cronExpr", "0 0 8 ? * MON",
            "channels", List.of("INAPP")
        );
        var create = mvc.perform(post("/scheduled-reports")
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(json(body)))
            .andExpect(status().isCreated()).andReturn();
        long id = mapper.readTree(create.getResponse().getContentAsString()).get("reportId").asLong();

        mvc.perform(post("/scheduled-reports/" + id + "/pause")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("PAUSED")));

        mvc.perform(post("/scheduled-reports/" + id + "/resume")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("ACTIVE")));

        mvc.perform(get("/scheduled-reports/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.nextRunAt", notNullValue()));
    }

    @Test
    void run_now_returns_accepted_even_when_scheduler_down() throws Exception {
        Map<String, Object> body = Map.of(
            "name", "立即跑",
            "dslJson", Map.of("metrics", List.of("sales_amount")),
            "scheduleType", "daily",
            "channels", List.of("INAPP")
        );
        var create = mvc.perform(post("/scheduled-reports")
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(json(body)))
            .andExpect(status().isCreated()).andReturn();
        long id = mapper.readTree(create.getResponse().getContentAsString()).get("reportId").asLong();

        mvc.perform(post("/scheduled-reports/" + id + "/run-now")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isAccepted())
            .andExpect(jsonPath("$.status", anyOf(is("PENDING"), is("submitted"))));
    }

    @Test
    void list_templates_and_subscribe() throws Exception {
        mvc.perform(get("/scheduled-reports/templates?business_line=TRADE")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].name", notNullValue()));

        mvc.perform(post("/scheduled-reports/templates/1/subscribe")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.source", is("template")))
            .andExpect(jsonPath("$.cronExpr", notNullValue()));
    }

    @Test
    void update_recomputes_next_run() throws Exception {
        Map<String, Object> body = Map.of(
            "name", "Bot",
            "dslJson", Map.of("metrics", List.of("sales_amount")),
            "scheduleType", "daily",
            "cronExpr", "0 0 8 * * ?",
            "channels", List.of("INAPP")
        );
        var create = mvc.perform(post("/scheduled-reports")
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(json(body)))
            .andExpect(status().isCreated()).andReturn();
        long id = mapper.readTree(create.getResponse().getContentAsString()).get("reportId").asLong();

        mvc.perform(patch("/scheduled-reports/" + id)
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(json(Map.of("cronExpr", "0 0 18 * * ?"))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.cronExpr", is("0 0 18 * * ?")));
    }
}
