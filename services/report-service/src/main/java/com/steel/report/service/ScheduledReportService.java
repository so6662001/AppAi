package com.steel.report.service;

import com.steel.report.client.SchedulerClient;
import com.steel.report.exception.NotFoundException;
import com.steel.report.model.*;
import com.steel.report.repo.*;
import com.steel.report.util.CronUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.*;

@Service
public class ScheduledReportService {

    private final ScheduledReportRepo repo;
    private final ReportRunRepo runRepo;
    private final ReportTemplateRepo templateRepo;
    private final SchedulerClient scheduler;

    @Autowired
    public ScheduledReportService(ScheduledReportRepo repo, ReportRunRepo runRepo,
                                  ReportTemplateRepo templateRepo, SchedulerClient scheduler) {
        this.repo = repo; this.runRepo = runRepo;
        this.templateRepo = templateRepo; this.scheduler = scheduler;
    }

    @Transactional
    public ScheduledReport create(ScheduledReport r, long tenantId, long userId) {
        r.setTenantId(tenantId);
        r.setUserId(userId);
        if (r.getStatus() == null) r.setStatus("ACTIVE");
        if (r.getTimezone() == null) r.setTimezone("Asia/Shanghai");
        r.setNextRunAt(CronUtil.nextRunAt(r.getScheduleType(), r.getCronExpr(),
            LocalDateTime.now(), r.getTimezone()));
        long id = repo.insert(r);
        return repo.findById(id);
    }

    public ScheduledReport get(long id) {
        ScheduledReport r = repo.findById(id);
        if (r == null) throw new NotFoundException("scheduled_report not found: " + id);
        return r;
    }

    public Map<String, Object> list(long tenantId, long userId, String status, int page, int size) {
        page = Math.max(1, page); size = Math.min(200, Math.max(1, size));
        List<ScheduledReport> items = repo.list(tenantId, userId, status, (page-1)*size, size);
        int total = repo.count(tenantId, userId, status);
        return Map.of("total", total, "page", page, "size", size, "items", items);
    }

    @Transactional
    public ScheduledReport update(long id, Map<String, Object> changes) {
        ScheduledReport before = get(id);
        repo.update(id, changes);
        // 修改 cron/scheduleType 后重算 next_run_at
        if (changes.containsKey("cronExpr") || changes.containsKey("scheduleType")
                || changes.containsKey("timezone")) {
            ScheduledReport r = repo.findById(id);
            LocalDateTime nxt = CronUtil.nextRunAt(r.getScheduleType(), r.getCronExpr(),
                LocalDateTime.now(), r.getTimezone());
            repo.update(id, Map.of("nextRunAt", nxt));
        }
        return repo.findById(id);
    }

    @Transactional
    public void delete(long id) {
        get(id);
        repo.softDelete(id);
    }

    @Transactional
    public void pause(long id) {
        get(id);
        repo.updateStatus(id, "PAUSED");
    }

    @Transactional
    public void resume(long id) {
        ScheduledReport r = get(id);
        repo.updateStatus(id, "ACTIVE");
        // 恢复后重算 next_run_at
        LocalDateTime nxt = CronUtil.nextRunAt(r.getScheduleType(), r.getCronExpr(),
            LocalDateTime.now(), r.getTimezone());
        repo.update(id, Map.of("nextRunAt", nxt));
    }

    public Map<String, Object> runNow(long id) {
        get(id);   // 校验存在
        Map<String, Object> ret = scheduler.runNow(id);
        return ret;
    }

    public List<ReportRun> runs(long reportId, int limit) {
        return runRepo.listByReport(reportId, Math.min(200, Math.max(1, limit)));
    }

    public ReportRun runDetail(long runId) {
        ReportRun r = runRepo.findById(runId);
        if (r == null) throw new NotFoundException("run not found: " + runId);
        return r;
    }

    // ============ 模板 ============
    public List<ReportTemplate> templates(String line, String role, String category) {
        return templateRepo.list(line, role, category);
    }

    @Transactional
    public ScheduledReport subscribeTemplate(long templateId, long tenantId, long userId) {
        ReportTemplate t = templateRepo.findById(templateId);
        if (t == null) throw new NotFoundException("template not found: " + templateId);

        ScheduledReport r = new ScheduledReport();
        r.setName(t.getName());
        r.setDescription(t.getDescription());
        r.setDslJson(t.getDslJson());
        r.setScheduleType("cron");
        r.setCronExpr(t.getCronExpr());
        r.setChannels(t.getChannels());
        r.setSource("template");

        ScheduledReport saved = create(r, tenantId, userId);
        templateRepo.incrPopularity(templateId);
        return saved;
    }
}
