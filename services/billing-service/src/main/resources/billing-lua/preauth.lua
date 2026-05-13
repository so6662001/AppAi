-- 占位: 实际启动时按 LUA_DIR 优先 (Docker 把 services/billing-lua/ 挂到容器)
-- 测试时 Mockito 模拟 LuaScriptManager.exec, 不读此文件
return {0, "PLACEHOLDER"}
