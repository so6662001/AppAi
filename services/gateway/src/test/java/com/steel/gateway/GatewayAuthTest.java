package com.steel.gateway;

import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import org.junit.jupiter.api.Test;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

import static org.junit.jupiter.api.Assertions.*;

/** 验证 JWT 签发与解析逻辑 (不依赖 Spring 上下文). */
class GatewayAuthTest {

    private final SecretKey key = Keys.hmacShaKeyFor(
        "change-me-to-a-strong-secret-at-least-32-bytes-long".getBytes(StandardCharsets.UTF_8));

    @Test
    void can_sign_and_parse_jwt() {
        String token = Jwts.builder()
            .subject("user-10")
            .claim("tenant_id", 1)
            .claim("biz", "TRADE")
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + 60_000))
            .signWith(key)
            .compact();

        var claims = Jwts.parser().verifyWith(key).build().parseSignedClaims(token).getPayload();
        assertEquals("user-10", claims.getSubject());
        assertEquals(1, ((Number) claims.get("tenant_id")).intValue());
        assertEquals("TRADE", claims.get("biz"));
    }

    @Test
    void tampered_token_is_rejected() {
        String token = Jwts.builder().subject("u").signWith(key).compact();
        String bad = token.substring(0, token.length() - 5) + "AAAAA";
        assertThrows(Exception.class, () -> Jwts.parser().verifyWith(key).build().parseSignedClaims(bad));
    }
}
