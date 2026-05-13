package com.steel.report.model;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
public class ScheduledReport {
    private Long reportId;
    private Long tenantId;
    private Long userId;
    private String name;
    private String description;

    private Map<String, Object> dslJson;
    private String question;
    private List<String> renderBlocks;
    private Map<String, Object> chartSpec;

    private String scheduleType;
    private String cronExpr;
    private String timezone = "Asia/Shanghai";
    private LocalDateTime nextRunAt;
    private LocalDateTime lastRunAt;
    private Integer failCount = 0;
    private String status = "ACTIVE";

    private List<String> recipients;
    private List<String> channels;
    private Boolean pushSilentIfEmpty = false;
    private String pushFormat = "card";
    private String notifyTemplate;

    private LocalDate effectiveFrom;
    private LocalDate effectiveTo;
    private Integer maxRunCount;

    private Long costOwnerUserId;
    private Long estimatedBizTokens;

    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
    private String source = "manual";
}
