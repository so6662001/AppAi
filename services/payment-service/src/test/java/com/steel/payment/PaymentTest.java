package com.steel.payment;

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
class PaymentTest {

    @Autowired MockMvc mvc;

    @Test
    void create_pay_notify_flow() throws Exception {
        var create = mvc.perform(post("/payment/orders").contentType("application/json")
                .content("{\"tenant_id\":1,\"plan_id\":10,\"pay_amount\":1299,\"pay_channel\":\"WECHAT\"}"))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.pay_status", is("PENDING")))
            .andReturn();

        String orderNo = com.fasterxml.jackson.databind.ObjectMapper.class.getDeclaredConstructor().newInstance()
            .readTree(create.getResponse().getContentAsString()).get("order_no").asText();
        long orderId = com.fasterxml.jackson.databind.ObjectMapper.class.getDeclaredConstructor().newInstance()
            .readTree(create.getResponse().getContentAsString()).get("order_id").asLong();

        mvc.perform(post("/payment/orders/" + orderId + "/pay"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.qr_code", notNullValue()));

        mvc.perform(post("/payment/notify/wechat").contentType("application/json")
                .content("{\"order_no\":\"" + orderNo + "\",\"status\":\"PAID\",\"trade_no\":\"WX123\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.status", is("ok")));

        mvc.perform(get("/payment/orders/" + orderId))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.pay_status", is("PAID")));
    }
}
