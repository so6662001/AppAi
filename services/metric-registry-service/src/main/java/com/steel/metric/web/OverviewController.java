package com.steel.metric.web;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@RestController
public class OverviewController {

    private final JdbcTemplate jdbc;

    @Autowired
    public OverviewController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    @GetMapping("/overview")
    public Map<String, Object> overview() {
        Integer total = jdbc.queryForObject("SELECT COUNT(*) FROM metric_def", Integer.class);
        var byStatus = jdbc.queryForList(
            "SELECT status, COUNT(*) AS n FROM metric_def GROUP BY status");
        Map<String, Integer> stat = new HashMap<>();
        for (var r : byStatus) {
            stat.put((String) r.get("status"), ((Number) r.get("n")).intValue());
        }
        var ownerTop = jdbc.queryForList(
            "SELECT owner, COUNT(*) AS count FROM metric_def "
          + "GROUP BY owner ORDER BY count DESC LIMIT 5");

        return Map.of(
            "total_metrics", total,
            "by_status", stat,
            "owner_top5", ownerTop,
            "sla_health", Map.of("healthy", total, "at_risk", 0, "failing", 0)
        );
    }
}
