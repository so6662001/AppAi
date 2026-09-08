package com.steel.report.repo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.steel.report.config.JsonHelper;
import com.steel.report.model.ReportRun;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.sql.Timestamp;
import java.util.List;
import java.util.Map;

@Repository
public class ReportRunRepo {

    private final JdbcTemplate jdbc;
    private final JsonHelper json;
    private final RowMapper<ReportRun> mapper;

    @Autowired
    public ReportRunRepo(JdbcTemplate jdbc, JsonHelper json) {
        this.jdbc = jdbc;
        this.json = json;
        this.mapper = buildMapper();
    }

    private RowMapper<ReportRun> buildMapper() {
        return (rs, n) -> {
        ReportRun r = new ReportRun();
        r.setRunId(rs.getLong("run_id"));
        r.setReportId(rs.getLong("report_id"));
        r.setTenantId(rs.getLong("tenant_id"));
        Timestamp t;
        t = rs.getTimestamp("scheduled_at"); if (t != null) r.setScheduledAt(t.toLocalDateTime());
        t = rs.getTimestamp("started_at");   if (t != null) r.setStartedAt(t.toLocalDateTime());
        t = rs.getTimestamp("finished_at");  if (t != null) r.setFinishedAt(t.toLocalDateTime());
        r.setDurationMs((Integer) rs.getObject("duration_ms"));
        r.setStatus(rs.getString("status"));
        r.setErrorCode(rs.getString("error_code"));
        r.setErrorMsg(rs.getString("error_msg"));
        r.setSqlText(rs.getString("sql_text"));
        r.setRowsReturned((Integer) rs.getObject("rows_returned"));
        r.setBlocksJson(json.fromJson(rs.getString("blocks_json"), new TypeReference<>() {}));
        r.setResultSummary(rs.getString("result_summary"));
        r.setResultArtifactUrl(rs.getString("result_artifact_url"));
        r.setPushResults(json.fromJson(rs.getString("push_results"), new TypeReference<>() {}));
        r.setBizTokensCharged((Long) rs.getObject("biz_tokens_charged"));
        r.setCostCny(rs.getObject("cost_cny") == null ? null : rs.getDouble("cost_cny"));
        r.setReservationId(rs.getString("reservation_id"));
        r.setMessageId(rs.getString("message_id"));
        return r;
        };
    }

    public List<ReportRun> listByReport(long reportId, int limit) {
        return jdbc.query(
            "SELECT * FROM scheduled_report_run WHERE report_id=? ORDER BY scheduled_at DESC LIMIT ?",
            mapper, reportId, limit);
    }

    public ReportRun findById(long runId) {
        List<ReportRun> list = jdbc.query(
            "SELECT * FROM scheduled_report_run WHERE run_id=?", mapper, runId);
        return list.isEmpty() ? null : list.get(0);
    }
}
