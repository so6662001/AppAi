package com.steel.billing.sweeper;

import com.steel.billing.service.ReservationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/** 每 30s 扫一次过期 HELD reservation, 自动 release. */
@Slf4j
@Component
public class ReservationSweeper {

    private final JdbcTemplate jdbc;
    private final ReservationService svc;

    @Autowired
    public ReservationSweeper(JdbcTemplate jdbc, ReservationService svc) {
        this.jdbc = jdbc; this.svc = svc;
    }

    @Scheduled(fixedDelayString = "30000")
    public void sweep() {
        List<Map<String, Object>> rows;
        try {
            rows = jdbc.queryForList(
                "SELECT reservation_id, tenant_id FROM usage_reservation "
              + "WHERE status='HELD' AND expires_at < NOW() LIMIT 200");
        } catch (Exception e) {
            // 表不存在(测试 H2)或库未启时不阻塞业务
            return;
        }
        for (var row : rows) {
            String rid = (String) row.get("reservation_id");
            long tid = ((Number) row.get("tenant_id")).longValue();
            try {
                svc.release(tid, rid);
                log.info("released expired reservation tid={} rid={}", tid, rid);
            } catch (Exception e) {
                log.warn("sweep release failed: {}", e.getMessage());
            }
        }
    }
}
