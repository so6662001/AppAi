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
class TenantNotifyConfigControllerTest {

    @Autowired MockMvc mvc;
    @Autowired ObjectMapper mapper;

    @Test
    void crud_wecom_webhook() throws Exception {
        // 创建
        Map<String, Object> body = Map.of(
            "channel", "WECOM",
            "name", "销售大区群机器人",
            "configJson", Map.of(
                "webhook", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
                "mention_mobiles", List.of("13800000000")
            ),
            "isDefault", true,
            "tags", List.of("sales", "weekly")
        );
        var create = mvc.perform(post("/notify-configs")
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(mapper.writeValueAsString(body)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.configId", notNullValue()))
            .andExpect(jsonPath("$.tenantId", is(1)))
            .andExpect(jsonPath("$.channel", is("WECOM")))
            .andReturn();
        long id = mapper.readTree(create.getResponse().getContentAsString()).get("configId").asLong();

        // 列表
        mvc.perform(get("/notify-configs?channel=WECOM")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$[0].configId", is((int) id)));

        // 更新
        mvc.perform(patch("/notify-configs/" + id)
                .contentType("application/json")
                .header("X-Tenant-Id", "1").header("X-User-Id", "10")
                .content(mapper.writeValueAsString(Map.of("name", "新名字"))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name", is("新名字")));

        // 删除
        mvc.perform(delete("/notify-configs/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isNoContent());

        // 删完拿不到
        mvc.perform(get("/notify-configs/" + id)
                .header("X-Tenant-Id", "1").header("X-User-Id", "10"))
            .andExpect(status().isNotFound());
    }
}
