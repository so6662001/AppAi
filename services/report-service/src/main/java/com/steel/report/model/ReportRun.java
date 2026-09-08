package com.steel.report.model;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
@NoArgsConstructor
public class ReportRun {
    private Long runId;
    private Long reportId;
    private Long tenantId;
    private LocalDateTime scheduledAt;
    private LocalDateTime startedAt;
    private LocalDateTime finishedAt;
    private Integer durationMs;
    private String status;          // PENDING/RUNNING/SUCCESS/FAILED/EMPTY/CANCELED
    private String errorCode;
    private String errorMsg;
    private String sqlText;
    private Integer rowsReturned;
    private List<Map<String, Object>> blocksJson;
    private String resultSummary;
    private String resultArtifactUrl;
    private List<Map<String, Object>> pushResults;
    private Long bizTokensCharged;
    private Double costCny;
    private String reservationId;
    private String messageId;
}
