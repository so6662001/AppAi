package com.steel.report.web;

import com.steel.report.model.TenantNotifyConfig;
import com.steel.report.service.TenantNotifyConfigService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/notify-configs")
public class TenantNotifyConfigController {

    private final TenantNotifyConfigService svc;
    private final AuthContext auth;

    @Autowired
    public TenantNotifyConfigController(TenantNotifyConfigService svc, AuthContext auth) {
        this.svc = svc; this.auth = auth;
    }

    @GetMapping
    public List<TenantNotifyConfig> list(@RequestParam(required = false) String channel) {
        return svc.list(auth.tenantId(), channel);
    }

    @GetMapping("/{id}")
    public TenantNotifyConfig get(@PathVariable long id) {
        return svc.get(id);
    }

    @PostMapping
    public ResponseEntity<TenantNotifyConfig> create(@RequestBody TenantNotifyConfig body) {
        TenantNotifyConfig saved = svc.create(body, auth.tenantId(), String.valueOf(auth.userId()));
        return ResponseEntity.status(201).body(saved);
    }

    @PatchMapping("/{id}")
    public TenantNotifyConfig update(@PathVariable long id, @RequestBody Map<String, Object> body) {
        return svc.update(id, body);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id) {
        svc.delete(id);
        return ResponseEntity.noContent().build();
    }
}
