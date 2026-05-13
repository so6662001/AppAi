package com.steel.report.model;

import lombok.Data;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@Data
public class TenantNotifyConfig {
    private Long configId;
    private Long tenantId;
    private String channel;       // WECOM/DINGTALK/EMAIL/UNI_PUSH/SMS/INAPP
    private String name;
    private Map<String, Object> configJson;
    private Boolean isDefault = false;
    private Boolean isActive = true;
    private List<String> tags;
    private String createdBy;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;
}
