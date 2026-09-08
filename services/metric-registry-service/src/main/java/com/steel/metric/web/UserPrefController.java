package com.steel.metric.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 用户偏好 / Onboarding / 个人 watch list.
 *
 * 接口:
 *   GET    /user/preferences                  我的偏好
 *   PUT    /user/preferences                  保存偏好 (Onboarding)
 *   GET    /user/visible-metrics              我能看到的全部指标 (汇总自 角色pack + 自订pack + watchList - hidden)
 *   POST   /user/watch                        添加个人关注指标
 *   DELETE /user/watch/{metricCode}           取消关注
 */
@RestController
@RequestMapping("/user")
public class UserPrefController {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    public UserPrefController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping("/preferences")
    public Map<String, Object> get(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId,
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId) {
        var rows = jdbc.queryForList(
            "SELECT * FROM sys_user_preferences WHERE user_id=?", userId);
        if (rows.isEmpty()) {
            return Map.of("user_id", userId, "tenant_id", tenantId, "onboarding_done", false);
        }
        return rows.get(0);
    }

    @PutMapping("/preferences")
    public Map<String, Object> save(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId,
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId,
            @RequestBody Map<String, Object> body) {
        try {
            jdbc.update(
                "INSERT INTO sys_user_preferences (user_id, tenant_id, business_line, "
              + "primary_role, interests_json, locale, onboarding_done, onboarding_at) "
              + "VALUES (?,?,?,?,?,?,1, NOW()) "
              + "ON DUPLICATE KEY UPDATE business_line=VALUES(business_line), "
              + "primary_role=VALUES(primary_role), interests_json=VALUES(interests_json), "
              + "locale=VALUES(locale), onboarding_done=1, onboarding_at=NOW()",
                userId, tenantId,
                body.get("business_line"), body.get("primary_role"),
                mapper.writeValueAsString(body.getOrDefault("interests", List.of())),
                body.getOrDefault("locale", "zh-CN"));
            return Map.of("status", "OK", "onboarding_done", true);
        } catch (Exception e) {
            return Map.of("status", "FAILED", "error", e.getMessage());
        }
    }

    @GetMapping("/visible-metrics")
    public Map<String, Object> visibleMetrics(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId,
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId) {
        // 1) 取用户偏好的 role 决定的 pack
        var prefs = jdbc.queryForList("SELECT * FROM sys_user_preferences WHERE user_id=?", userId);
        java.util.Set<String> metricSet = new java.util.LinkedHashSet<>();
        String role = null;
        if (!prefs.isEmpty()) {
            role = (String) prefs.get(0).get("primary_role");
            // 角色对应的 pack
            if (role != null) {
                addMetricsFromPacks(jdbc.queryForList(
                    "SELECT metrics_json FROM metric_pack WHERE role_code=? AND is_active=1", role),
                    metricSet);
            }
            // 用户额外订阅的 pack
            Object cpRaw = prefs.get(0).get("custom_pack_ids");
            if (cpRaw != null) {
                try {
                    List<String> ids = mapper.readValue(cpRaw.toString(), List.class);
                    for (String id : ids) {
                        addMetricsFromPacks(jdbc.queryForList(
                            "SELECT metrics_json FROM metric_pack WHERE pack_id=?", id),
                            metricSet);
                    }
                } catch (Exception ignored) {}
            }
            // 个人 watch list
            Object cmRaw = prefs.get(0).get("custom_metrics");
            if (cmRaw != null) {
                try {
                    List<String> metrics = mapper.readValue(cmRaw.toString(), List.class);
                    metricSet.addAll(metrics);
                } catch (Exception ignored) {}
            }
        }
        return Map.of(
            "user_id", userId,
            "primary_role", role,
            "metrics", new java.util.ArrayList<>(metricSet),
            "count", metricSet.size()
        );
    }

    @SuppressWarnings("unchecked")
    private void addMetricsFromPacks(List<Map<String, Object>> rows, java.util.Set<String> sink) {
        for (var row : rows) {
            Object raw = row.get("metrics_json");
            if (raw == null) continue;
            String s = raw.toString();
            if ("ALL".equalsIgnoreCase(s.replace("\"", ""))) {
                // ALL 表示全部, 留个标记
                sink.add("__ALL__"); return;
            }
            try {
                List<String> ms = mapper.readValue(s, List.class);
                sink.addAll(ms);
            } catch (Exception ignored) {}
        }
    }

    @PostMapping("/watch")
    public Map<String, Object> addWatch(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId,
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId,
            @RequestBody Map<String, Object> body) {
        String metricCode = (String) body.get("metric_code");
        try {
            var rows = jdbc.queryForList(
                "SELECT custom_metrics FROM sys_user_preferences WHERE user_id=?", userId);
            List<String> ms = new java.util.ArrayList<>();
            if (!rows.isEmpty() && rows.get(0).get("custom_metrics") != null) {
                try { ms = mapper.readValue(rows.get(0).get("custom_metrics").toString(), List.class); }
                catch (Exception ignored) {}
            }
            if (!ms.contains(metricCode)) ms.add(metricCode);
            jdbc.update(
                "INSERT INTO sys_user_preferences (user_id, tenant_id, custom_metrics) VALUES (?,?,?) "
              + "ON DUPLICATE KEY UPDATE custom_metrics=VALUES(custom_metrics)",
                userId, tenantId, mapper.writeValueAsString(ms));
            return Map.of("status", "OK", "metric_code", metricCode);
        } catch (Exception e) {
            return Map.of("status", "FAILED", "error", e.getMessage());
        }
    }

    @DeleteMapping("/watch/{metricCode}")
    public Map<String, Object> removeWatch(
            @PathVariable String metricCode,
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId) {
        try {
            var rows = jdbc.queryForList(
                "SELECT custom_metrics FROM sys_user_preferences WHERE user_id=?", userId);
            if (rows.isEmpty()) return Map.of("status", "OK");
            List<String> ms = mapper.readValue(
                rows.get(0).get("custom_metrics").toString(), List.class);
            ms.remove(metricCode);
            jdbc.update(
                "UPDATE sys_user_preferences SET custom_metrics=? WHERE user_id=?",
                mapper.writeValueAsString(ms), userId);
            return Map.of("status", "OK");
        } catch (Exception e) {
            return Map.of("status", "FAILED", "error", e.getMessage());
        }
    }
}
