package com.steel.report.web;

import com.steel.report.model.ReportRun;
import com.steel.report.model.ReportTemplate;
import com.steel.report.model.ScheduledReport;
import com.steel.report.service.ScheduledReportService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/scheduled-reports")
public class ScheduledReportController {

    private final ScheduledReportService svc;
    private final AuthContext auth;

    @Autowired
    public ScheduledReportController(ScheduledReportService svc, AuthContext auth) {
        this.svc = svc; this.auth = auth;
    }

    @GetMapping
    public Map<String, Object> list(@RequestParam(required = false) String status,
                                    @RequestParam(defaultValue = "1") int page,
                                    @RequestParam(defaultValue = "30") int size) {
        return svc.list(auth.tenantId(), auth.userId(), status, page, size);
    }

    @PostMapping
    public ResponseEntity<ScheduledReport> create(@RequestBody ScheduledReport body) {
        ScheduledReport r = svc.create(body, auth.tenantId(), auth.userId());
        return ResponseEntity.status(201).body(r);
    }

    @GetMapping("/{id}")
    public ScheduledReport get(@PathVariable long id) {
        return svc.get(id);
    }

    @PatchMapping("/{id}")
    public ScheduledReport update(@PathVariable long id, @RequestBody Map<String, Object> body) {
        return svc.update(id, body);
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id) {
        svc.delete(id);
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/{id}/pause")
    public Map<String, Object> pause(@PathVariable long id) {
        svc.pause(id);
        return Map.of("status", "PAUSED");
    }

    @PostMapping("/{id}/resume")
    public Map<String, Object> resume(@PathVariable long id) {
        svc.resume(id);
        return Map.of("status", "ACTIVE");
    }

    @PostMapping("/{id}/run-now")
    public ResponseEntity<Map<String, Object>> runNow(@PathVariable long id) {
        return ResponseEntity.accepted().body(svc.runNow(id));
    }

    @GetMapping("/{id}/runs")
    public List<ReportRun> runs(@PathVariable long id,
                                @RequestParam(defaultValue = "30") int limit) {
        return svc.runs(id, limit);
    }

    @GetMapping("/runs/{runId}")
    public ReportRun runDetail(@PathVariable long runId) {
        return svc.runDetail(runId);
    }

    // ============ 模板 ============
    @GetMapping("/templates")
    public List<ReportTemplate> templates(
        @RequestParam(name = "business_line", required = false) String line,
        @RequestParam(required = false) String role,
        @RequestParam(required = false) String category) {
        return svc.templates(line, role, category);
    }

    @PostMapping("/templates/{tplId}/subscribe")
    public ResponseEntity<ScheduledReport> subscribe(@PathVariable long tplId) {
        ScheduledReport r = svc.subscribeTemplate(tplId, auth.tenantId(), auth.userId());
        return ResponseEntity.status(201).body(r);
    }
}
