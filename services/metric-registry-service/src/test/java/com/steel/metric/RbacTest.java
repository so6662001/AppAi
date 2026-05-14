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
class RbacTest {

    @Autowired MockMvc mvc;

    @Test
    void create_user_assign_role() throws Exception {
        // 建用户
        mvc.perform(post("/rbac/users").contentType("application/json")
                .content("{\"tenant_id\":1,\"username\":\"alice\",\"display_name\":\"爱丽丝\",\"email\":\"a@x.com\"}"))
           .andExpect(status().isCreated());
        // 建角色
        mvc.perform(post("/rbac/roles").contentType("application/json")
                .content("{\"tenant_id\":1,\"role_code\":\"SALES\",\"role_name\":\"销售\"}"))
           .andExpect(status().isCreated());
        // 列出
        mvc.perform(get("/rbac/users?tenant_id=1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].username", is("alice")));
        mvc.perform(get("/rbac/roles?tenant_id=1"))
           .andExpect(status().isOk());

        // 列出权限点
        mvc.perform(get("/rbac/permissions"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].perm_code", notNullValue()));

        // 分配角色
        mvc.perform(post("/rbac/users/1/roles").contentType("application/json")
                .content("{\"role_id\":1}"))
           .andExpect(status().isCreated());
        mvc.perform(get("/rbac/users/1/roles"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].role_code", is("SALES")));
    }

    @Test
    void row_acl_set_and_get() throws Exception {
        mvc.perform(post("/rbac/users").contentType("application/json")
                .content("{\"tenant_id\":1,\"username\":\"bob\"}"))
           .andExpect(status().isCreated());

        mvc.perform(post("/rbac/users/2/row-acl").contentType("application/json")
                .content("{\"resource\":\"org\",\"resource_ids\":[100,101]}"))
           .andExpect(status().isCreated());

        mvc.perform(get("/rbac/users/2/row-acl"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$[0].resource", is("org")));
    }
}
