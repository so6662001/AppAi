package com.steel.report.model;

import lombok.Data;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class ReportTemplate {
    private Long templateId;
    private String businessLine;
    private String role;
    private String category;
    private String name;
    private String description;
    private Map<String, Object> dslJson;
    private String cronExpr;
    private List<String> channels;
    private Integer popularity = 0;
    private Boolean isActive = true;
    private LocalDateTime createdAt;
}
