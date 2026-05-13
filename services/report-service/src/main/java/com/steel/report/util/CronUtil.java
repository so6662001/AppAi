package com.steel.report.util;

import org.springframework.scheduling.support.CronExpression;
import java.time.LocalDateTime;
import java.time.ZoneId;
import java.time.ZonedDateTime;

public final class CronUtil {

    /** 由 schedule_type + cron_expr 推算下次执行时间。
     *  Spring CronExpression 用 6 段(秒/分/时/日/月/周), 与本系统一致。
     */
    public static LocalDateTime nextRunAt(String scheduleType, String cronExpr,
                                          LocalDateTime base, String tz) {
        if ("once".equalsIgnoreCase(scheduleType)) return null;

        String expr = cronExpr;
        if (expr == null || expr.isBlank()) {
            switch (scheduleType == null ? "" : scheduleType) {
                case "daily":   expr = "0 0 8 * * *"; break;
                case "weekly":  expr = "0 0 8 * * 1"; break;
                case "monthly": expr = "0 0 8 1 * *"; break;
                default: return null;
            }
        }
        // Spring CronExpression 不接受 '?', 替换为 '*'
        expr = expr.replace('?', '*');
        CronExpression cron = CronExpression.parse(expr);
        ZonedDateTime z = base.atZone(ZoneId.of(tz == null ? "Asia/Shanghai" : tz));
        ZonedDateTime next = cron.next(z);
        return next == null ? null : next.toLocalDateTime();
    }
}
