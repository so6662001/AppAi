package com.steel.metric.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/metrics")
public class MetricController {

    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    public MetricController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping
    public Map<String, Object> list(
            @RequestParam(required = false) String q,
            @RequestParam(required = false) String domain,
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String sensitivity,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "50") int size) {

        StringBuilder where = new StringBuilder("WHERE 1=1 ");
        List<Object> args = new java.util.ArrayList<>();
        if (q != null && !q.isEmpty()) {
            where.append("AND (metric_code LIKE ? OR name LIKE ? OR name_zh LIKE ?) ");
            args.add("%" + q + "%"); args.add("%" + q + "%"); args.add("%" + q + "%");
        }
        if (domain != null)      { where.append("AND domain=? "); args.add(domain); }
        if (status != null)      { where.append("AND status=? "); args.add(status); }
        if (sensitivity != null) { where.append("AND sensitivity=? "); args.add(sensitivity); }

        int offset = Math.max(0, (page - 1) * size);
        Integer total = jdbc.queryForObject(
            "SELECT COUNT(*) FROM metric_def " + where, Integer.class, args.toArray());

        List<Object> args2 = new java.util.ArrayList<>(args);
        args2.add(size); args2.add(offset);
        List<Map<String, Object>> items = jdbc.queryForList(
            "SELECT metric_code, name, name_zh, domain, version, status, sensitivity, owner, "
          + "updated_at FROM metric_def " + where + "ORDER BY updated_at DESC LIMIT ? OFFSET ?",
            args2.toArray());

        return Map.of("total", total, "page", page, "size", size, "items", items);
    }

    @GetMapping("/{code}")
    public ResponseEntity<Map<String, Object>> get(@PathVariable String code) {
        var list = jdbc.queryForList("SELECT * FROM metric_def WHERE metric_code=?", code);
        if (list.isEmpty()) return ResponseEntity.notFound().build();
        return ResponseEntity.ok(list.get(0));
    }

    @PostMapping
    public ResponseEntity<Map<String, Object>> create(@RequestBody Map<String, Object> body) {
        // 走变更申请, 非直接落表; 简化版直接 insert
        try {
            jdbc.update(
                "INSERT INTO metric_def (metric_code, name, name_zh, domain, formula, "
              + "semantics, status, owner, version) VALUES (?,?,?,?,?,?,?,?,?)",
                body.get("metric_code"), body.get("name"), body.get("name_zh"),
                body.get("domain"), body.get("formula"),
                body.getOrDefault("semantics", "additive"),
                body.getOrDefault("status", "DRAFT"),
                body.getOrDefault("owner", "unknown"),
                body.getOrDefault("version", "0.1.0"));
            return ResponseEntity.status(201).body(Map.of("status", "created", "code", body.get("metric_code")));
        } catch (Exception e) {
            return ResponseEntity.badRequest().body(Map.of("error", e.getMessage()));
        }
    }

    @PatchMapping("/{code}")
    public Map<String, Object> patch(@PathVariable String code, @RequestBody Map<String, Object> body) {
        // 简化: 直接 update 受白名单字段
        List<String> sets = new java.util.ArrayList<>();
        List<Object> args = new java.util.ArrayList<>();
        for (String k : List.of("name_zh", "formula", "status", "owner", "sensitivity",
                                  "notes", "version")) {
            if (body.containsKey(k)) {
                sets.add(k + "=?"); args.add(body.get(k));
            }
        }
        if (sets.isEmpty()) return Map.of("status", "no_change");
        args.add(code);
        jdbc.update("UPDATE metric_def SET " + String.join(",", sets) + " WHERE metric_code=?",
                    args.toArray());
        return Map.of("status", "updated", "code", code);
    }

    @DeleteMapping("/{code}")
    public ResponseEntity<Void> deprecate(@PathVariable String code) {
        jdbc.update("UPDATE metric_def SET status='DEPRECATED' WHERE metric_code=?", code);
        return ResponseEntity.noContent().build();
    }

    // 影响分析 + 血缘
    @GetMapping("/{code}/impact")
    public Map<String, Object> impact(@PathVariable String code) {
        // 下游依赖 - 用 LIKE 兼容 H2/MySQL (生产 MySQL 推荐 JSON_CONTAINS)
        var downstream = jdbc.queryForList(
            "SELECT metric_code, name_zh FROM metric_def WHERE requires_metrics LIKE ?",
            "%\"" + code + "\"%");
        // 看板/会话引用
        Integer dashCount = jdbc.queryForObject(
            "SELECT COUNT(*) FROM metric_usage_ref WHERE metric_code=? AND ref_type='DASHBOARD'",
            Integer.class, code);
        Integer sessionCount = jdbc.queryForObject(
            "SELECT COUNT(*) FROM metric_usage_ref WHERE metric_code=? AND ref_type='AI_SESSION'",
            Integer.class, code);

        String risk = "LOW";
        if (downstream.size() > 2 || dashCount > 3) risk = "MEDIUM";
        if (downstream.size() > 5 || dashCount > 10 || sessionCount > 100) risk = "HIGH";

        Map<String, Object> out = new HashMap<>();
        out.put("downstream_metrics", downstream);
        out.put("dashboards", dashCount);
        out.put("ai_sessions_7d", sessionCount);
        out.put("risk_level", risk);
        return out;
    }

    @GetMapping("/{code}/lineage")
    public Map<String, Object> lineage(@PathVariable String code,
                                       @RequestParam(defaultValue = "2") int depth) {
        // 简化版血缘: 拉直接上下游
        var m = jdbc.queryForList(
            "SELECT requires_metrics FROM metric_def WHERE metric_code=?", code);
        var downstream = jdbc.queryForList(
            "SELECT metric_code FROM metric_def WHERE requires_metrics LIKE ?",
            "%\"" + code + "\"%");

        List<Map<String, Object>> nodes = new java.util.ArrayList<>();
        List<Map<String, Object>> edges = new java.util.ArrayList<>();
        nodes.add(Map.of("id", code, "type", "metric", "center", true));
        for (var d : downstream) {
            nodes.add(Map.of("id", d.get("metric_code"), "type", "metric"));
            edges.add(Map.of("from", code, "to", d.get("metric_code")));
        }
        if (!m.isEmpty() && m.get(0).get("requires_metrics") != null) {
            try {
                List<String> upstream = mapper.readValue(m.get(0).get("requires_metrics").toString(), List.class);
                for (String u : upstream) {
                    nodes.add(Map.of("id", u, "type", "metric"));
                    edges.add(Map.of("from", u, "to", code));
                }
            } catch (Exception ignored) {}
        }
        return Map.of("nodes", nodes, "edges", edges);
    }
}
