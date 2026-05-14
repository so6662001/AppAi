package com.steel.metric.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 指标包 CRUD + 用户绑定.
 *
 * 接口:
 *   GET    /metric-packs                            列表
 *   GET    /metric-packs?business_line=TRADE         按业务过滤
 *   GET    /metric-packs/{pack_id}                  详情 (含完整指标 + 推荐问题)
 *   POST   /metric-packs                            新建 (自定义包)
 *   PATCH  /metric-packs/{pack_id}                  编辑
 *   DELETE /metric-packs/{pack_id}                  停用 (is_active=0)
 *   POST   /metric-packs/{pack_id}/subscribe        用户订阅此包
 *   DELETE /metric-packs/{pack_id}/subscribe        用户退订
 *   GET    /metric-packs/recommend                  ?role=SALES_REP&biz=TRADE → 给新用户推荐
 *
 * 集成: chat-orchestrator / briefing-service 启动时拉用户的 pack, 决定其可见指标
 */
@RestController
@RequestMapping("/metric-packs")
public class MetricPackController {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    public MetricPackController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(required = false) String business_line,
            @RequestParam(required = false) String role_code) {
        StringBuilder sql = new StringBuilder(
            "SELECT pack_id, name, description, business_line, role_code, metric_count, "
          + "popularity, is_system FROM metric_pack WHERE is_active=1 ");
        List<Object> args = new java.util.ArrayList<>();
        if (business_line != null) { sql.append("AND business_line IN (?,'ALL') "); args.add(business_line); }
        if (role_code != null)     { sql.append("AND role_code=? "); args.add(role_code); }
        sql.append("ORDER BY popularity DESC, pack_id ASC");
        var items = jdbc.queryForList(sql.toString(), args.toArray());
        return Map.of("total", items.size(), "items", items);
    }

    @GetMapping("/{packId}")
    public ResponseEntity<Map<String, Object>> get(@PathVariable String packId) {
        var rows = jdbc.queryForList("SELECT * FROM metric_pack WHERE pack_id=?", packId);
        if (rows.isEmpty()) return ResponseEntity.notFound().build();
        return ResponseEntity.ok(rows.get(0));
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@RequestBody Map<String, Object> body) {
        try {
            jdbc.update("INSERT INTO metric_pack (pack_id, name, description, business_line, "
                  + "role_code, metrics_json, summary_kpis_json, recommended_questions_json, "
                  + "metric_count, is_system) VALUES (?,?,?,?,?,?,?,?,?,0)",
                body.get("pack_id"), body.get("name"), body.get("description"),
                body.get("business_line"), body.get("role_code"),
                mapper.writeValueAsString(body.getOrDefault("metrics", List.of())),
                mapper.writeValueAsString(body.getOrDefault("summary_kpis", List.of())),
                mapper.writeValueAsString(body.getOrDefault("recommended_questions", List.of())),
                ((List<?>) body.getOrDefault("metrics", List.of())).size());
            return ResponseEntity.status(201).body(Map.of("status", "created", "pack_id", body.get("pack_id")));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PatchMapping("/{packId}")
    public Map<String, Object> patch(@PathVariable String packId, @RequestBody Map<String, Object> body) {
        List<String> sets = new java.util.ArrayList<>();
        List<Object> args = new java.util.ArrayList<>();
        for (String k : List.of("name", "description", "is_active")) {
            if (body.containsKey(k)) { sets.add(k + "=?"); args.add(body.get(k)); }
        }
        if (sets.isEmpty()) return Map.of("status", "no_change");
        args.add(packId);
        jdbc.update("UPDATE metric_pack SET " + String.join(",", sets) + " WHERE pack_id=?",
                    args.toArray());
        return Map.of("status", "updated");
    }

    @DeleteMapping("/{packId}")
    public ResponseEntity<Void> deactivate(@PathVariable String packId) {
        jdbc.update("UPDATE metric_pack SET is_active=0 WHERE pack_id=?", packId);
        return ResponseEntity.noContent().build();
    }

    /** 根据角色 + 业务推荐包 (Onboarding 用). */
    @GetMapping("/recommend")
    public Map<String, Object> recommend(
            @RequestParam(required = false) String biz,
            @RequestParam(required = false) String role) {
        StringBuilder sql = new StringBuilder(
            "SELECT * FROM metric_pack WHERE is_active=1 ");
        List<Object> args = new java.util.ArrayList<>();
        if (role != null) { sql.append("AND role_code=? "); args.add(role); }
        if (biz != null)  { sql.append("AND business_line IN (?, 'ALL') "); args.add(biz); }
        sql.append("ORDER BY popularity DESC LIMIT 5");
        var packs = jdbc.queryForList(sql.toString(), args.toArray());
        return Map.of("primary", packs.isEmpty() ? null : packs.get(0),
                      "alternatives", packs.size() > 1 ? packs.subList(1, packs.size()) : List.of());
    }

    /** 用户订阅一个包. 调用方需带 X-User-Id. */
    @PostMapping("/{packId}/subscribe")
    public ResponseEntity<Map<String, Object>> subscribe(
            @PathVariable String packId,
            @org.springframework.web.bind.annotation.RequestHeader(value = "X-User-Id", defaultValue = "1") long userId) {
        try {
            jdbc.update("UPDATE metric_pack SET popularity = popularity + 1 WHERE pack_id=?", packId);
            // 写入 sys_user_preferences.custom_pack_ids (append)
            var rows = jdbc.queryForList(
                "SELECT custom_pack_ids FROM sys_user_preferences WHERE user_id=?", userId);
            List<String> ids = new java.util.ArrayList<>();
            if (!rows.isEmpty() && rows.get(0).get("custom_pack_ids") != null) {
                try {
                    ids = mapper.readValue(rows.get(0).get("custom_pack_ids").toString(), List.class);
                } catch (Exception ignored) {}
            }
            if (!ids.contains(packId)) ids.add(packId);
            jdbc.update(
                "INSERT INTO sys_user_preferences (user_id, tenant_id, custom_pack_ids) VALUES (?, 1, ?) "
              + "ON DUPLICATE KEY UPDATE custom_pack_ids=VALUES(custom_pack_ids)",
                userId, mapper.writeValueAsString(ids));
            return ResponseEntity.status(201).body(Map.of("status", "subscribed", "pack_id", packId));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }
}
