package com.steel.report.repo;

import com.fasterxml.jackson.core.type.TypeReference;
import com.steel.report.config.JsonHelper;
import com.steel.report.model.TenantNotifyConfig;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.simple.SimpleJdbcInsert;
import org.springframework.stereotype.Repository;

import javax.sql.DataSource;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Repository
public class TenantNotifyConfigRepo {

    private final JdbcTemplate jdbc;
    private final SimpleJdbcInsert insert;
    private final JsonHelper json;
    private final RowMapper<TenantNotifyConfig> mapper;

    @Autowired
    public TenantNotifyConfigRepo(JdbcTemplate jdbc, DataSource ds, JsonHelper json) {
        this.jdbc = jdbc; this.json = json;
        this.insert = new SimpleJdbcInsert(ds)
            .withTableName("tenant_notify_config")
            .usingGeneratedKeyColumns("config_id");
        this.mapper = buildMapper();
    }

    private RowMapper<TenantNotifyConfig> buildMapper() {
        return (rs, n) -> {
        TenantNotifyConfig c = new TenantNotifyConfig();
        c.setConfigId(rs.getLong("config_id"));
        c.setTenantId(rs.getLong("tenant_id"));
        c.setChannel(rs.getString("channel"));
        c.setName(rs.getString("name"));
        c.setConfigJson(json.fromJson(rs.getString("config_json"), new TypeReference<>() {}));
        c.setIsDefault(rs.getInt("is_default") != 0);
        c.setIsActive(rs.getInt("is_active") != 0);
        c.setTags(json.fromJson(rs.getString("tags"), new TypeReference<>() {}));
        c.setCreatedBy(rs.getString("created_by"));
        java.sql.Timestamp ca = rs.getTimestamp("created_at"); if (ca != null) c.setCreatedAt(ca.toLocalDateTime());
        java.sql.Timestamp ua = rs.getTimestamp("updated_at"); if (ua != null) c.setUpdatedAt(ua.toLocalDateTime());
        return c;
        };
    }

    public List<TenantNotifyConfig> listByTenant(long tenantId, String channel) {
        StringBuilder sql = new StringBuilder(
            "SELECT * FROM tenant_notify_config WHERE tenant_id=? AND is_active=1 ");
        List<Object> args = new java.util.ArrayList<>();
        args.add(tenantId);
        if (channel != null) { sql.append("AND channel=? "); args.add(channel); }
        sql.append("ORDER BY is_default DESC, config_id ASC");
        return jdbc.query(sql.toString(), mapper, args.toArray());
    }

    public TenantNotifyConfig findById(long id) {
        List<TenantNotifyConfig> list = jdbc.query(
            "SELECT * FROM tenant_notify_config WHERE config_id=?", mapper, id);
        return list.isEmpty() ? null : list.get(0);
    }

    public long insert(TenantNotifyConfig c) {
        Map<String, Object> v = new HashMap<>();
        v.put("tenant_id", c.getTenantId());
        v.put("channel", c.getChannel());
        v.put("name", c.getName());
        v.put("config_json", json.toJson(c.getConfigJson()));
        v.put("is_default", c.getIsDefault() ? 1 : 0);
        v.put("is_active", c.getIsActive() ? 1 : 0);
        v.put("tags", json.toJson(c.getTags()));
        v.put("created_by", c.getCreatedBy());
        return insert.executeAndReturnKey(v).longValue();
    }

    public int update(long id, Map<String, Object> fields) {
        if (fields.isEmpty()) return 0;
        List<String> sets = new java.util.ArrayList<>();
        List<Object> args = new java.util.ArrayList<>();
        Map<String, String> map = Map.of(
            "name", "name", "configJson", "config_json", "isDefault", "is_default",
            "isActive", "is_active", "tags", "tags"
        );
        for (var e : fields.entrySet()) {
            String col = map.get(e.getKey()); if (col == null) continue;
            sets.add(col + "=?");
            Object v = e.getValue();
            if (v instanceof Map || v instanceof List) v = json.toJson(v);
            else if (v instanceof Boolean) v = ((Boolean) v) ? 1 : 0;
            args.add(v);
        }
        if (sets.isEmpty()) return 0;
        args.add(id);
        return jdbc.update(
            "UPDATE tenant_notify_config SET " + String.join(",", sets) + " WHERE config_id=?",
            args.toArray());
    }

    public int delete(long id) {
        return jdbc.update("DELETE FROM tenant_notify_config WHERE config_id=?", id);
    }
}
