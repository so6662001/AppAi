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
        // TODO: 校验 JWT 中的 tenant_id 与请求体中的一致, 防越权
    }
}
