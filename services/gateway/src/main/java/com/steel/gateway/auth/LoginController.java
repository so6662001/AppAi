package com.steel.gateway.auth;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;
import java.util.Map;

/**
 * 简化登录 (demo): 用户名密码 → 颁发 JWT.
 * 生产对接现有 ERP SSO / OAuth2 / LDAP 等.
 */
@RestController
@RequestMapping("/v1/auth")
public class LoginController {

    private final SecretKey key;
    private final long expireSec;

    public LoginController(@Value("${auth.jwt-secret}") String secret,
                           @Value("${auth.token-expire-seconds:86400}") long expireSec) {
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.expireSec = expireSec;
    }

    @PostMapping("/login")
    public ResponseEntity<Map<String, Object>> login(@RequestBody Map<String, Object> body) {
        String username = (String) body.get("username");
        String password = (String) body.get("password");
        if (username == null || password == null) {
            return ResponseEntity.badRequest().body(Map.of("error", "username & password required"));
        }
        // 占位: 真实环境查 user 表 / 调 ERP SSO 校验
        if (!"demo".equals(password)) {
            return ResponseEntity.status(401).body(Map.of("error", "invalid credentials"));
        }
        long now = System.currentTimeMillis();
        String token = Jwts.builder()
            .subject(username)
            .claim("tenant_id", body.getOrDefault("tenant_id", 1))
            .claim("biz", body.getOrDefault("business_line", "TRADE"))
            .claim("role", body.getOrDefault("role", "USER"))
            .issuedAt(new Date(now))
            .expiration(new Date(now + expireSec * 1000))
            .signWith(key)
            .compact();
        return ResponseEntity.ok(Map.of(
            "token", token, "type", "Bearer",
            "expires_in", expireSec, "user", username));
    }
}
