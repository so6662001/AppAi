package com.steel.billing.lua;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.data.redis.core.script.RedisScript;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 加载 services/billing-lua/*.lua 脚本, 启动时 SCRIPT LOAD,
 * 之后通过 sha1 直接 EVALSHA 调用.
 *
 * 与项目 README 一致:
 *  - preauth.lua : KEYS=[wallet, resv], ARGV=[estimate, need_times, allow_overrun, now_ms, tid, uid, sid, mid]
 *  - settle.lua  : KEYS=[wallet, resv], ARGV=[actual, now_ms, allow_overrun]
 *  - release.lua : KEYS=[wallet, resv], ARGV=[now_ms]
 *  - refund.lua  : KEYS=[wallet],       ARGV=[account, amount, now_ms, ref_id]
 */
@Slf4j
@Component
public class LuaScriptManager {

    private final StringRedisTemplate redis;
    private final ResourceLoader resourceLoader;
    private final Path luaDir;

    private final Map<String, RedisScript<List>> scripts = new HashMap<>();

    public LuaScriptManager(StringRedisTemplate redis, ResourceLoader resourceLoader,
                            @Value("${billing.lua-dir:/app/billing-lua}") String luaDir) {
        this.redis = redis;
        this.resourceLoader = resourceLoader;
        this.luaDir = Path.of(luaDir);
    }

    @PostConstruct
    public void load() {
        for (String name : List.of("preauth", "settle", "release", "refund")) {
            String body = loadLuaBody(name + ".lua");
            DefaultRedisScript<List> s = new DefaultRedisScript<>();
            s.setScriptText(body);
            s.setResultType(List.class);
            scripts.put(name, s);
            log.info("loaded lua script: {} ({} bytes)", name, body.length());
        }
    }

    private String loadLuaBody(String filename) {
        // 1. 先看磁盘
        Path p = luaDir.resolve(filename);
        if (Files.exists(p)) {
            try {
                return Files.readString(p, StandardCharsets.UTF_8);
            } catch (IOException e) {
                log.warn("read lua from disk failed: {}", e.getMessage());
            }
        }
        // 2. 再看 classpath (打包时一起进 jar)
        Resource r = resourceLoader.getResource("classpath:billing-lua/" + filename);
        if (r.exists()) {
            try {
                return new String(r.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            } catch (IOException e) {
                throw new RuntimeException("load lua " + filename + " failed", e);
            }
        }
        throw new IllegalStateException("lua not found: " + filename
            + " (luaDir=" + luaDir + ", classpath=billing-lua/" + filename + ")");
    }

    /** 调用脚本. args 一律用 List 而非 varargs, 便于 Mockito 匹配. */
    @SuppressWarnings("unchecked")
    public List<Object> exec(String name, List<String> keys, List<Object> args) {
        RedisScript<List> s = scripts.get(name);
        if (s == null) throw new IllegalArgumentException("unknown lua: " + name);
        String[] argStr = new String[args.size()];
        for (int i = 0; i < args.size(); i++) argStr[i] = String.valueOf(args.get(i));
        return redis.execute(s, keys, (Object[]) argStr);
    }
}
