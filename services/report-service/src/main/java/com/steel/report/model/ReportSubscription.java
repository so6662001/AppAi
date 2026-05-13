package com.steel.report.model;

import lombok.Data;
import java.time.LocalDateTime;
import java.util.List;

@Data
public class ReportSubscription {
    private Long subId;
    private Long reportId;
    private Long tenantId;
    private Long subscriberUserId;
    private List<String> channels;
    private String status = "ACTIVE";
    private LocalDateTime createdAt;
}
