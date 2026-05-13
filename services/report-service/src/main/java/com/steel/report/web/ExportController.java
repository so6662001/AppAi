package com.steel.report.web;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.steel.report.model.ReportRun;
import com.steel.report.repo.ReportRunRepo;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.io.PrintWriter;
import java.util.List;
import java.util.Map;

/**
 * 导出执行结果为 CSV/Excel.
 * 当前实现 CSV (无需额外依赖). Excel(POI) 建议后续在独立微服务里做.
 */
@RestController
@RequestMapping("/scheduled-reports")
public class ExportController {

    private final ReportRunRepo runRepo;
    private final ObjectMapper mapper = new ObjectMapper();

    @Autowired
    public ExportController(ReportRunRepo runRepo) { this.runRepo = runRepo; }

    @GetMapping("/runs/{runId}/export")
    public void export(@org.springframework.web.bind.annotation.PathVariable long runId,
                       @RequestParam(defaultValue = "csv") String format,
                       HttpServletResponse resp) throws IOException {
        ReportRun r = runRepo.findById(runId);
        if (r == null) { resp.setStatus(404); return; }

        List<Map<String, Object>> rows = r.getBlocksJson() == null ? List.of()
            : extractTableRows(r.getBlocksJson());

        resp.setContentType("text/csv; charset=utf-8");
        resp.setHeader("Content-Disposition",
            "attachment; filename=report_" + runId + ".csv");
        PrintWriter w = resp.getWriter();
        w.write("\uFEFF");          // UTF-8 BOM 让 Excel 正确识别中文
        if (rows.isEmpty()) {
            w.write("(no data)\n");
            return;
        }
        List<String> cols = new java.util.ArrayList<>(rows.get(0).keySet());
        w.write(String.join(",", cols) + "\n");
        for (var row : rows) {
            List<String> vs = new java.util.ArrayList<>();
            for (String c : cols) {
                Object v = row.get(c);
                String s = v == null ? "" : v.toString().replace(",", " ").replace("\n", " ");
                vs.add(s);
            }
            w.write(String.join(",", vs) + "\n");
        }
        w.flush();
    }

    @SuppressWarnings("unchecked")
    private List<Map<String, Object>> extractTableRows(List<Map<String, Object>> blocks) {
        for (var b : blocks) {
            if ("table".equals(b.get("type"))) {
                return (List<Map<String, Object>>) b.getOrDefault("rows", List.of());
            }
        }
        return List.of();
    }
}
