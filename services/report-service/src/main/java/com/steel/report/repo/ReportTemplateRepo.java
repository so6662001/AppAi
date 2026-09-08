package com.steel.report.repo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.steel.report.config.JsonHelper;
import com.steel.report.model.ReportTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.ArrayList;
import java.util.List;

@Repository
public class ReportTemplateRepo {
    private final JdbcTemplate jdbc;
    private final JsonHelper json;
    private final RowMapper<ReportTemplate> mapper;

    @Autowired
    public ReportTemplateRepo(JdbcTemplate jdbc, JsonHelper json) {
        this.jdbc = jdbc; this.json = json;
        this.mapper = buildMapper();
    }

    private RowMapper<ReportTemplate> buildMapper() {
        return (rs, n) -> {
        ReportTemplate t = new ReportTemplate();
        t.setTemplateId(rs.getLong("template_id"));
        t.setBusinessLine(rs.getString("business_line"));
        t.setRole(rs.getString("role"));
        t.setCategory(rs.getString("category"));
        t.setName(rs.getString("name"));
        t.setDescription(rs.getString("description"));
        t.setDslJson(json.fromJson(rs.getString("dsl_json"), new TypeReference<>() {}));
        t.setCronExpr(rs.getString("cron_expr"));
        t.setChannels(json.fromJson(rs.getString("channels"), new TypeReference<>() {}));
        t.setPopularity(rs.getInt("popularity"));
        t.setIsActive(rs.getInt("is_active") != 0);
        java.sql.Timestamp ca = rs.getTimestamp("created_at"); if (ca != null) t.setCreatedAt(ca.toLocalDateTime());
        return t;
        };
    }

    public List<ReportTemplate> list(String businessLine, String role, String category) {
        StringBuilder sql = new StringBuilder(
            "SELECT * FROM scheduled_report_template WHERE is_active=1 ");
        List<Object> args = new ArrayList<>();
        if (businessLine != null) { sql.append("AND business_line=? "); args.add(businessLine); }
        if (role != null)         { sql.append("AND role=? ");          args.add(role); }
        if (category != null)     { sql.append("AND category=? ");      args.add(category); }
        sql.append("ORDER BY popularity DESC, template_id ASC");
        return jdbc.query(sql.toString(), mapper, args.toArray());
    }

    public ReportTemplate findById(long id) {
        List<ReportTemplate> list = jdbc.query(
            "SELECT * FROM scheduled_report_template WHERE template_id=?", mapper, id);
        return list.isEmpty() ? null : list.get(0);
    }

    public int incrPopularity(long id) {
        return jdbc.update(
            "UPDATE scheduled_report_template SET popularity=popularity+1 WHERE template_id=?", id);
    }
}
