package com.steel.billing.model;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.List;
import java.util.Map;

@Data @NoArgsConstructor @AllArgsConstructor
public class Reservation {
    private String reservationId;
    private Long   tenantId;
    private Long   userId;
    private String sessionId;
    private String messageId;
    private Long   estimate;
    /** 占用计划: 每项 = {b: SUB/TIMES/TOKEN/OVERRUN, h: 持有量, [times|cent]} */
    private List<Map<String, Object>> plan;
}
