package com.steel.metric.web;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * RBAC 用户/角色/权限/行列 ACL 管理接口.
 */
@RestController
@RequestMapping("/rbac")
public class RbacController {

    private final JdbcTemplate jdbc;
    public RbacController(JdbcTemplate jdbc) { this.jdbc = jdbc; }

    // ============ 用户 ============
    @GetMapping("/users")
    public List<Map<String, Object>> users(
            @RequestParam(defaultValue = "1") long tenant_id) {
        return jdbc.queryForList(
            "SELECT user_id, username, display_name, email, phone, is_active FROM sys_user "
          + "WHERE tenant_id=? ORDER BY user_id DESC", tenant_id);
    }

    @PostMapping("/users")
    public ResponseEntity<Map<String, Object>> createUser(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.getOrDefault("tenant_id", 1)).longValue();
        jdbc.update("INSERT INTO sys_user (tenant_id, username, display_name, email, phone, "
                  + "password_hash, is_active) VALUES (?,?,?,?,?,?,1)",
            tid, body.get("username"), body.get("display_name"),
            body.get("email"), body.get("phone"),
            body.get("password_hash"));
        return ResponseEntity.status(201).body(Map.of("status", "created"));
    }

    @DeleteMapping("/users/{id}")
    public ResponseEntity<Void> deleteUser(@PathVariable long id) {
        jdbc.update("UPDATE sys_user SET is_active=0 WHERE user_id=?", id);
        return ResponseEntity.noContent().build();
    }

    // ============ 角色 ============
    @GetMapping("/roles")
    public List<Map<String, Object>> roles(@RequestParam(defaultValue = "1") long tenant_id) {
        return jdbc.queryForList(
            "SELECT * FROM sys_role WHERE tenant_id=? AND is_active=1", tenant_id);
    }

    @PostMapping("/roles")
    public ResponseEntity<Map<String, Object>> createRole(@RequestBody Map<String, Object> body) {
        long tid = ((Number) body.getOrDefault("tenant_id", 1)).longValue();
        jdbc.update("INSERT INTO sys_role (tenant_id, role_code, role_name) VALUES (?,?,?)",
            tid, body.get("role_code"), body.get("role_name"));
        return ResponseEntity.status(201).body(Map.of("status", "created"));
    }

    // ============ 权限点 ============
    @GetMapping("/permissions")
    public List<Map<String, Object>> permissions() {
        return jdbc.queryForList("SELECT * FROM sys_permission");
    }

    // ============ 用户-角色 ============
    @GetMapping("/users/{userId}/roles")
    public List<Map<String, Object>> userRoles(@PathVariable long userId) {
        return jdbc.queryForList(
            "SELECT r.* FROM sys_role r JOIN sys_user_role ur ON ur.role_id = r.role_id "
          + "WHERE ur.user_id=?", userId);
    }

    @PostMapping("/users/{userId}/roles")
    public ResponseEntity<Map<String, Object>> assignRole(
            @PathVariable long userId, @RequestBody Map<String, Object> body) {
        long roleId = ((Number) body.get("role_id")).longValue();
        try {
            jdbc.update("INSERT INTO sys_user_role (user_id, role_id) VALUES (?, ?)",
                userId, roleId);
        } catch (Exception ignored) {}
        return ResponseEntity.status(201).body(Map.of("status", "assigned"));
    }

    @DeleteMapping("/users/{userId}/roles/{roleId}")
    public ResponseEntity<Void> revokeRole(@PathVariable long userId, @PathVariable long roleId) {
        jdbc.update("DELETE FROM sys_user_role WHERE user_id=? AND role_id=?", userId, roleId);
        return ResponseEntity.noContent().build();
    }

    // ============ 角色-权限 ============
    @PostMapping("/roles/{roleId}/permissions")
    public ResponseEntity<Map<String, Object>> grantPerm(
            @PathVariable long roleId, @RequestBody Map<String, Object> body) {
        long permId = ((Number) body.get("perm_id")).longValue();
        try {
            jdbc.update("INSERT INTO sys_role_permission (role_id, perm_id) VALUES (?, ?)",
                roleId, permId);
        } catch (Exception ignored) {}
        return ResponseEntity.status(201).body(Map.of("status", "granted"));
    }

    // ============ 行级权限 ============
    @PostMapping("/users/{userId}/row-acl")
    public ResponseEntity<Map<String, Object>> setRowAcl(
            @PathVariable long userId, @RequestBody Map<String, Object> body) {
        String resource = (String) body.get("resource");
        Object ids = body.get("resource_ids");
        jdbc.update("INSERT INTO sys_row_acl (user_id, resource, resource_ids) VALUES (?,?,?)",
            userId, resource, ids == null ? "[]" : ids.toString());
        return ResponseEntity.status(201).body(Map.of("status", "set"));
    }

    @GetMapping("/users/{userId}/row-acl")
    public List<Map<String, Object>> getRowAcl(@PathVariable long userId) {
        return jdbc.queryForList("SELECT * FROM sys_row_acl WHERE user_id=?", userId);
    }
}
