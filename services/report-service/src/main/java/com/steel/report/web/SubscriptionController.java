package com.steel.report.web;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/scheduled-reports/{id}/subscribers")
public class SubscriptionController {

    private final JdbcTemplate jdbc;
    private final AuthContext auth;

    @Autowired
    public SubscriptionController(JdbcTemplate jdbc, AuthContext auth) {
        this.jdbc = jdbc; this.auth = auth;
    }

    @GetMapping
    public List<Map<String, Object>> list(@PathVariable long id) {
        return jdbc.queryForList(
            "SELECT * FROM scheduled_report_subscription WHERE report_id=? AND tenant_id=? "
          + "AND status<>'UNSUBSCRIBED'",
            id, auth.tenantId());
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> add(@PathVariable long id, @RequestBody Map<String, Object> body) {
        long userId = ((Number) body.get("user_id")).longValue();
        Object channels = body.getOrDefault("channels", null);
        try {
            jdbc.update(
                "INSERT INTO scheduled_report_subscription (report_id, tenant_id, "
              + "subscriber_user_id, channels, status) VALUES (?,?,?,?,'ACTIVE')",
                id, auth.tenantId(), userId,
                channels == null ? null : channels.toString());
            return ResponseEntity.status(201).body(Map.of("status", "created"));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @DeleteMapping("/{subId}")
    public ResponseEntity<Void> remove(@PathVariable long id, @PathVariable long subId) {
        jdbc.update("UPDATE scheduled_report_subscription SET status='UNSUBSCRIBED' "
                    + "WHERE sub_id=? AND report_id=?", subId, id);
        return ResponseEntity.noContent().build();
    }
}
