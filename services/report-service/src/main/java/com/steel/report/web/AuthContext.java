package com.steel.report.web;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Component;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import java.util.Optional;

/**
 * 从请求头解析 tenant/user, 实际项目应解析 JWT.
 * 测试 + 开发环境直接读 X-Tenant-Id / X-User-Id 头.
 */
@Component
public class AuthContext {

    public long tenantId() {
        return Optional.ofNullable(req())
            .map(r -> r.getHeader("X-Tenant-Id"))
            .map(Long::parseLong).orElse(1L);
    }

    public long userId() {
        return Optional.ofNullable(req())
            .map(r -> r.getHeader("X-User-Id"))
            .map(Long::parseLong).orElse(1L);
    }

    private HttpServletRequest req() {
        try {
            return ((ServletRequestAttributes)
                RequestContextHolder.currentRequestAttributes()).getRequest();
        } catch (Exception e) { return null; }
    }
}
