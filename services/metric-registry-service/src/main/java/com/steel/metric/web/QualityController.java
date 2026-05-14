package com.steel.metric.web;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.util.*;

@RestController
@RequestMapping("/quality")
public class QualityController {

    private final JdbcTemplate jdbc;
    public QualityController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    /** SLA 健康度热力图 matrix: 每个 (metric_code, date) 一个 sla_pct. */
    @GetMapping("/sla-heatmap")
    public Map<String, Object> slaHeatmap(@RequestParam(defaultValue = "30") int days,
                                          @RequestParam(required = false) String domain) {
        List<Map<String, Object>> matrix = new ArrayList<>();

        // 取所有 PUBLISHED 指标
        var metrics = jdbc.queryForList(
            "SELECT metric_code FROM metric_def WHERE status='PUBLISHED'" +
            (domain != null ? " AND domain='" + domain.replaceAll("[^A-Z_]", "") + "'" : "") +
            " LIMIT 100");

        for (int i = days - 1; i >= 0; i--) {
            LocalDate d = LocalDate.now().minusDays(i);
            for (var m : metrics) {
                String code = (String) m.get("metric_code");
                // 当日质量事件数 → 估算 SLA
                Integer events = jdbc.queryForObject(
                    "SELECT COUNT(*) FROM metric_quality_event WHERE metric_code=? "
                  + "AND DATE(detected_at)=? AND resolved_at IS NULL",
                    Integer.class, code, d);
                double slaPct = events == 0 ? 100.0 : Math.max(0.0, 100.0 - events * 20.0);
                matrix.add(Map.of("metric_code", code, "date", d.toString(),
                                   "sla_pct", slaPct,
                                   "status", slaPct >= 95 ? "HEALTHY" :
                                             slaPct >= 80 ? "AT_RISK" : "FAILING"));
            }
        }
        return Map.of("matrix", matrix, "days", days);
    }

    /** 质量事件列表 */
    @GetMapping("/events")
    public List<Map<String, Object>> events(
            @RequestParam(required = false) String metric_code,
            @RequestParam(required = false) String severity,
            @RequestParam(defaultValue = "OPEN") String status) {
        StringBuilder sql = new StringBuilder("SELECT * FROM metric_quality_event WHERE 1=1 ");
        List<Object> args = new ArrayList<>();
        if (metric_code != null) { sql.append("AND metric_code=? "); args.add(metric_code); }
        if (severity != null)    { sql.append("AND severity=? "); args.add(severity); }
        if ("OPEN".equals(status)) sql.append("AND resolved_at IS NULL ");
        else if ("RESOLVED".equals(status)) sql.append("AND resolved_at IS NOT NULL ");
        sql.append("ORDER BY detected_at DESC LIMIT 200");
        return jdbc.queryForList(sql.toString(), args.toArray());
    }

    @PostMapping("/events/{id}/resolve")
    public Map<String, Object> resolve(@PathVariable long id) {
        jdbc.update("UPDATE metric_quality_event SET resolved_at=CURRENT_TIMESTAMP WHERE event_id=?", id);
        return Map.of("status", "OK");
    }
}
