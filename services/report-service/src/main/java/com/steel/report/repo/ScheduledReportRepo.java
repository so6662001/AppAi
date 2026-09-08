package com.steel.report.repo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.steel.report.config.JsonHelper;
import com.steel.report.model.ScheduledReport;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.SimpleJdbcInsert;
import org.springframework.stereotype.Repository;

import javax.sql.DataSource;
import java.sql.Timestamp;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Repository
public class ScheduledReportRepo {

    private final JdbcTemplate jdbc;
    private final SimpleJdbcInsert insert;
    private final JsonHelper json;
    private final RowMapper<ScheduledReport> mapper;

    @Autowired
    public ScheduledReportRepo(JdbcTemplate jdbc, DataSource ds, JsonHelper json) {
        this.jdbc = jdbc;
        this.json = json;
        this.insert = new SimpleJdbcInsert(ds)
            .withTableName("scheduled_report")
            .usingGeneratedKeyColumns("report_id");
        this.mapper = buildMapper();
    }

    private RowMapper<ScheduledReport> buildMapper() {
        return (rs, n) -> {
        ScheduledReport r = new ScheduledReport();
        r.setReportId(rs.getLong("report_id"));
        r.setTenantId(rs.getLong("tenant_id"));
        r.setUserId(rs.getLong("user_id"));
        r.setName(rs.getString("name"));
        r.setDescription(rs.getString("description"));
        r.setDslJson(json.fromJson(rs.getString("dsl_json"), new TypeReference<Map<String,Object>>(){}));
        r.setQuestion(rs.getString("question"));
        r.setRenderBlocks(json.fromJson(rs.getString("render_blocks"), new TypeReference<List<String>>(){}));
        r.setChartSpec(json.fromJson(rs.getString("chart_spec"), new TypeReference<Map<String,Object>>(){}));
        r.setScheduleType(rs.getString("schedule_type"));
        r.setCronExpr(rs.getString("cron_expr"));
        r.setTimezone(rs.getString("timezone"));
        Timestamp nx = rs.getTimestamp("next_run_at"); r.setNextRunAt(nx == null ? null : nx.toLocalDateTime());
        Timestamp lx = rs.getTimestamp("last_run_at"); r.setLastRunAt(lx == null ? null : lx.toLocalDateTime());
        r.setFailCount(rs.getInt("fail_count"));
        r.setStatus(rs.getString("status"));
        r.setRecipients(json.fromJson(rs.getString("recipients"), new TypeReference<List<String>>(){}));
        r.setChannels(json.fromJson(rs.getString("channels"), new TypeReference<List<String>>(){}));
        r.setPushSilentIfEmpty(rs.getInt("push_silent_if_empty") != 0);
        r.setPushFormat(rs.getString("push_format"));
        r.setNotifyTemplate(rs.getString("notify_template"));
        java.sql.Date ef = rs.getDate("effective_from"); if (ef != null) r.setEffectiveFrom(ef.toLocalDate());
        java.sql.Date et = rs.getDate("effective_to");   if (et != null) r.setEffectiveTo(et.toLocalDate());
        r.setMaxRunCount((Integer) rs.getObject("max_run_count"));
        r.setCostOwnerUserId((Long) rs.getObject("cost_owner_user_id"));
        r.setEstimatedBizTokens((Long) rs.getObject("estimated_biz_tokens"));
        Timestamp ca = rs.getTimestamp("created_at"); if (ca != null) r.setCreatedAt(ca.toLocalDateTime());
        Timestamp ua = rs.getTimestamp("updated_at"); if (ua != null) r.setUpdatedAt(ua.toLocalDateTime());
        r.setSource(rs.getString("source"));
        return r;
        };
    }

    public ScheduledReport findById(long id) {
        List<ScheduledReport> list = jdbc.query(
            "SELECT * FROM scheduled_report WHERE report_id = ? AND status <> 'DELETED'",
            mapper, id);
        return list.isEmpty() ? null : list.get(0);
    }

    public List<ScheduledReport> list(long tenantId, long userId, String status, int offset, int size) {
        StringBuilder sql = new StringBuilder(
            "SELECT * FROM scheduled_report WHERE tenant_id=? AND user_id=? AND status<>'DELETED' ");
        List<Object> args = new java.util.ArrayList<>();
        args.add(tenantId); args.add(userId);
        if (status != null && !status.isEmpty()) {
            sql.append("AND status=? ");
            args.add(status);
        }
        sql.append("ORDER BY updated_at DESC LIMIT ? OFFSET ?");
        args.add(size); args.add(offset);
        return jdbc.query(sql.toString(), mapper, args.toArray());
    }

    public int count(long tenantId, long userId, String status) {
        StringBuilder sql = new StringBuilder(
            "SELECT COUNT(*) FROM scheduled_report WHERE tenant_id=? AND user_id=? AND status<>'DELETED' ");
        List<Object> args = new java.util.ArrayList<>();
        args.add(tenantId); args.add(userId);
        if (status != null && !status.isEmpty()) { sql.append("AND status=? "); args.add(status); }
        return jdbc.queryForObject(sql.toString(), Integer.class, args.toArray());
    }

    public long insert(ScheduledReport r) {
        Map<String, Object> v = new HashMap<>();
        v.put("tenant_id", r.getTenantId());
        v.put("user_id", r.getUserId());
        v.put("name", r.getName());
        v.put("description", r.getDescription());
        v.put("dsl_json", json.toJson(r.getDslJson()));
        v.put("question", r.getQuestion());
        v.put("render_blocks", json.toJson(r.getRenderBlocks()));
        v.put("chart_spec", json.toJson(r.getChartSpec()));
        v.put("schedule_type", r.getScheduleType());
        v.put("cron_expr", r.getCronExpr());
        v.put("timezone", r.getTimezone());
        v.put("next_run_at", r.getNextRunAt());
        v.put("status", r.getStatus());
        v.put("recipients", json.toJson(r.getRecipients()));
        v.put("channels", json.toJson(r.getChannels()));
        v.put("push_silent_if_empty", r.getPushSilentIfEmpty() ? 1 : 0);
        v.put("push_format", r.getPushFormat());
        v.put("notify_template", r.getNotifyTemplate());
        v.put("effective_from", r.getEffectiveFrom());
        v.put("effective_to", r.getEffectiveTo());
        v.put("max_run_count", r.getMaxRunCount());
        v.put("cost_owner_user_id", r.getCostOwnerUserId() != null ? r.getCostOwnerUserId() : r.getUserId());
        v.put("estimated_biz_tokens", r.getEstimatedBizTokens());
        v.put("source", r.getSource());
        return insert.executeAndReturnKey(v).longValue();
    }

    public int update(long id, Map<String, Object> fields) {
        if (fields.isEmpty()) return 0;
        List<String> sets = new java.util.ArrayList<>();
        List<Object> args = new java.util.ArrayList<>();
        Map<String, String> map = Map.ofEntries(
            Map.entry("name", "name"), Map.entry("description", "description"),
            Map.entry("dslJson", "dsl_json"), Map.entry("question", "question"),
            Map.entry("renderBlocks", "render_blocks"), Map.entry("chartSpec", "chart_spec"),
            Map.entry("scheduleType", "schedule_type"), Map.entry("cronExpr", "cron_expr"),
            Map.entry("timezone", "timezone"), Map.entry("nextRunAt", "next_run_at"),
            Map.entry("status", "status"), Map.entry("recipients", "recipients"),
            Map.entry("channels", "channels"), Map.entry("pushSilentIfEmpty", "push_silent_if_empty"),
            Map.entry("pushFormat", "push_format"), Map.entry("effectiveTo", "effective_to")
        );
        for (var e : fields.entrySet()) {
            String col = map.get(e.getKey());
            if (col == null) continue;
            sets.add(col + "=?");
            Object v = e.getValue();
            if (v instanceof Map || v instanceof List) v = json.toJson(v);
            else if (v instanceof Boolean) v = ((Boolean) v) ? 1 : 0;
            args.add(v);
        }
        if (sets.isEmpty()) return 0;
        args.add(id);
        return jdbc.update("UPDATE scheduled_report SET " + String.join(",", sets) + " WHERE report_id=?",
            args.toArray());
    }

    public int softDelete(long id) {
        return jdbc.update("UPDATE scheduled_report SET status='DELETED' WHERE report_id=?", id);
    }

    public int updateStatus(long id, String status) {
        return jdbc.update("UPDATE scheduled_report SET status=? WHERE report_id=?", status, id);
    }
}
