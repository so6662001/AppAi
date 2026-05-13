package com.steel.report.service;

import com.steel.report.exception.NotFoundException;
import com.steel.report.model.TenantNotifyConfig;
import com.steel.report.repo.TenantNotifyConfigRepo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Map;

@Service
public class TenantNotifyConfigService {

    private final TenantNotifyConfigRepo repo;

    @Autowired
    public TenantNotifyConfigService(TenantNotifyConfigRepo repo) { this.repo = repo; }

    public List<TenantNotifyConfig> list(long tenantId, String channel) {
        return repo.listByTenant(tenantId, channel);
    }

    public TenantNotifyConfig get(long id) {
        TenantNotifyConfig c = repo.findById(id);
        if (c == null) throw new NotFoundException("notify config not found: " + id);
        return c;
    }

    public TenantNotifyConfig create(TenantNotifyConfig c, long tenantId, String creator) {
        c.setTenantId(tenantId);
        c.setCreatedBy(creator);
        if (c.getIsDefault() == null) c.setIsDefault(false);
        if (c.getIsActive() == null) c.setIsActive(true);
        return repo.findById(repo.insert(c));
    }

    public TenantNotifyConfig update(long id, Map<String, Object> fields) {
        get(id);
        repo.update(id, fields);
        return repo.findById(id);
    }

    public void delete(long id) {
        get(id);
        repo.delete(id);
    }
}
