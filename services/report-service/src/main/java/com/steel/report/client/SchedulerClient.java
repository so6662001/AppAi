package com.steel.report.client;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.util.Map;

@Component
public class SchedulerClient {

    private final RestClient client;

    public SchedulerClient(@Value("${scheduler.base-url:http://localhost:8100}") String baseUrl) {
        this.client = RestClient.builder().baseUrl(baseUrl).build();
    }

    /** 调用 report-scheduler 立即执行某报表; 返回 (status, runId)。 */
    public Map<String, Object> runNow(long reportId) {
        try {
            return client.post()
                .uri("/internal/run-now/{id}", reportId)
                .retrieve()
                .body(Map.class);
        } catch (RestClientException e) {
            // 调度器不可达时返回 PENDING, 由调度器下一轮扫描自然触发
            return Map.of("status", "PENDING", "report_id", reportId, "error", e.getMessage());
        }
    }
}
