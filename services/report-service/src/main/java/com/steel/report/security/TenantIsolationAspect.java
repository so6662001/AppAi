package com.steel.report.security;

import com.steel.report.web.AuthContext;
import org.aspectj.lang.JoinPoint;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Before;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * 多租户隔离切面 - 在 Controller 进入前校验 X-Tenant-Id 必须 > 0.
 * 真实场景应验证 JWT 中的 tenant_id 与 URL/Body 中的 tenant_id 一致.
 *
 * 启用: 主类加 @EnableAspectJAutoProxy (Spring Boot 默认已启用).
 * 引入: 在 pom.xml 加 spring-boot-starter-aop 即可生效.
 */
@Aspect
@Component
public class TenantIsolationAspect {

    private final AuthContext auth;

    @Autowired
    public TenantIsolationAspect(AuthContext auth) { this.auth = auth; }

    @Before("execution(* com.steel.report.web..*Controller.*(..))")
    public void checkTenant(JoinPoint jp) {
        long tid = auth.tenantId();
        if (tid <= 0) {
            throw new SecurityException("invalid tenant_id");
        }
        // 严格校验: 扫描参数中所有 Map / Bean 的 tenantId 字段, 必须与 header 一致
        for (Object arg : jp.getArgs()) {
            if (arg == null) continue;
            Long inBody = null;
            if (arg instanceof java.util.Map) {
                Object v = ((java.util.Map<?, ?>) arg).get("tenant_id");
                if (v == null) v = ((java.util.Map<?, ?>) arg).get("tenantId");
                if (v instanceof Number) inBody = ((Number) v).longValue();
            } else {
                try {
                    var f = arg.getClass().getMethod("getTenantId");
                    Object v = f.invoke(arg);
                    if (v instanceof Number) inBody = ((Number) v).longValue();
                } catch (NoSuchMethodException ignored) {
                } catch (Exception ignored) {}
            }
            if (inBody != null && inBody != tid) {
                throw new SecurityException(
                    "tenant_id mismatch: header=" + tid + " body=" + inBody);
            }
        }
    }
}
