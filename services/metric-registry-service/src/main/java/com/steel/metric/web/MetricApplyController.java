package com.steel.metric.web;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 用户申请扩展权限 / Owner 审批.
 *
 * 接口:
 *   POST   /metric-apply                       提交申请
 *   GET    /metric-apply/my                    我的申请
 *   GET    /metric-apply/pending               待我审批 (Owner/Admin)
 *   POST   /metric-apply/{id}/approve          批准 (可加 duration_days 临时授权)
 *   POST   /metric-apply/{id}/reject           拒绝
 */
@RestController
@RequestMapping("/metric-apply")
public class MetricApplyController {

    private final JdbcTemplate jdbc;
    public MetricApplyController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @PostMapping
    public ResponseEntity<Map<String, Object>> apply(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId,
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId,
            @RequestBody Map<String, Object> body) {
        try {
            jdbc.update(
                "INSERT INTO sys_metric_apply (tenant_id, user_id, metric_code, scope_code, "
              + "reason, duration_days, status) VALUES (?,?,?,?,?,?,'PENDING')",
                tenantId, userId,
                body.get("metric_code"), body.get("scope_code"),
                body.get("reason"), body.get("duration_days"));
            return ResponseEntity.status(201).body(Map.of("status", "PENDING"));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @GetMapping("/my")
    public List<Map<String, Object>> myApplies(
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long userId) {
        return jdbc.queryForList(
            "SELECT * FROM sys_metric_apply WHERE user_id=? ORDER BY created_at DESC LIMIT 50",
            userId);
    }

    @GetMapping("/pending")
    public List<Map<String, Object>> pending(
            @RequestHeader(value = "X-Tenant-Id", defaultValue = "1") long tenantId) {
        return jdbc.queryForList(
            "SELECT a.*, u.username, u.display_name FROM sys_metric_apply a "
          + "LEFT JOIN sys_user u ON u.user_id = a.user_id "
          + "WHERE a.tenant_id=? AND a.status='PENDING' "
          + "ORDER BY a.created_at ASC", tenantId);
    }

    @PostMapping("/{id}/approve")
    public Map<String, Object> approve(
            @PathVariable long id,
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long reviewerId,
            @RequestBody(required = false) Map<String, Object> body) {
        body = body == null ? Map.of() : body;
        try {
            var rows = jdbc.queryForList("SELECT * FROM sys_metric_apply WHERE apply_id=?", id);
            if (rows.isEmpty()) return Map.of("error", "not found");
            var a = rows.get(0);
            // 1. 更新申请状态
            jdbc.update("UPDATE sys_metric_apply SET status='APPROVED', reviewer_id=?, "
                      + "review_comment=?, reviewed_at=NOW() WHERE apply_id=?",
                reviewerId, body.get("comment"), id);
            // 2. 写 sys_user_temp_grant 或 sys_user_role
            Integer days = (Integer) a.get("duration_days");
            if (days != null && days > 0) {
                // 临时授权 - 用 Java 算 expires_at, 避免 SQL 方言差异
                java.time.LocalDateTime expiresAt = java.time.LocalDateTime.now().plusDays(days);
                jdbc.update(
                    "INSERT INTO sys_user_temp_grant (user_id, scope_code, metric_code, "
                  + "reason, granted_by, expires_at) VALUES (?,?,?,?,?,?)",
                    a.get("user_id"), a.get("scope_code"), a.get("metric_code"),
                    a.get("reason"), reviewerId, java.sql.Timestamp.valueOf(expiresAt));
            }
            // (永久授权由 Admin 手动加角色)
            return Map.of("status", "APPROVED", "duration_days", days);
        } catch (Exception e) {
            return Map.of("status", "FAILED", "error", e.getMessage());
        }
    }

    @PostMapping("/{id}/reject")
    public Map<String, Object> reject(
            @PathVariable long id,
            @RequestHeader(value = "X-User-Id", defaultValue = "1") long reviewerId,
            @RequestBody(required = false) Map<String, Object> body) {
        body = body == null ? Map.of() : body;
        try {
            jdbc.update("UPDATE sys_metric_apply SET status='REJECTED', reviewer_id=?, "
                      + "review_comment=?, reviewed_at=NOW() WHERE apply_id=?",
                reviewerId, body.get("comment"), id);
            return Map.of("status", "REJECTED");
        } catch (Exception e) {
            return Map.of("status", "FAILED", "error", e.getMessage());
        }
    }
}
