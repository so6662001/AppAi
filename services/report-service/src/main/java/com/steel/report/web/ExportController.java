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

        if ("xlsx".equalsIgnoreCase(format)) {
            exportXlsx(rows, runId, resp);
        } else {
            exportCsv(rows, runId, resp);
        }
    }

    private void exportCsv(List<Map<String, Object>> rows, long runId,
                           HttpServletResponse resp) throws IOException {
        resp.setContentType("text/csv; charset=utf-8");
        resp.setHeader("Content-Disposition", "attachment; filename=report_" + runId + ".csv");
        PrintWriter w = resp.getWriter();
        w.write("\uFEFF");
        if (rows.isEmpty()) { w.write("(no data)\n"); return; }
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

    private void exportXlsx(List<Map<String, Object>> rows, long runId,
                            HttpServletResponse resp) throws IOException {
        resp.setContentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet");
        resp.setHeader("Content-Disposition", "attachment; filename=report_" + runId + ".xlsx");
        try (var wb = new org.apache.poi.xssf.streaming.SXSSFWorkbook(100)) {
            var sheet = wb.createSheet("Report");
            if (rows.isEmpty()) {
                sheet.createRow(0).createCell(0).setCellValue("(no data)");
                wb.write(resp.getOutputStream());
                return;
            }
            List<String> cols = new java.util.ArrayList<>(rows.get(0).keySet());
            var headerStyle = wb.createCellStyle();
            var font = wb.createFont(); font.setBold(true);
            headerStyle.setFont(font);
            var hr = sheet.createRow(0);
            for (int i = 0; i < cols.size(); i++) {
                var cell = hr.createCell(i);
                cell.setCellValue(cols.get(i));
                cell.setCellStyle(headerStyle);
            }
            int ri = 1;
            for (var row : rows) {
                var sr = sheet.createRow(ri++);
                for (int i = 0; i < cols.size(); i++) {
                    Object v = row.get(cols.get(i));
                    var cell = sr.createCell(i);
                    if (v == null) cell.setCellValue("");
                    else if (v instanceof Number) cell.setCellValue(((Number) v).doubleValue());
                    else cell.setCellValue(v.toString());
                }
            }
            wb.write(resp.getOutputStream());
        }
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
