--[[
  release.lua — 释放预扣 (用户中断/超时清扫)
  KEYS: [1] wallet:{tid}, [2] resv:{rid}
  ARGV: [1] now_ms
  返回: { 1, "RELEASED" } / { 0, err }
]]--

local wallet = KEYS[1]
local resv   = KEYS[2]
local now_ms = tonumber(ARGV[1])

if redis.call('EXISTS', resv) == 0 then
  return {0, "RESV_NOT_FOUND"}
end

local status = redis.call('HGET', resv, 'status')
if status == 'SETTLED' then
  return {0, "ALREADY_SETTLED"}
end
if status == 'RELEASED' then
  return {1, "ALREADY_RELEASED"}
end

local function hgeti(k, f)
  local v = redis.call('HGET', k, f)
  return tonumber(v) or 0
end

local plan_json = redis.call('HGET', resv, 'plan')
local plan = cjson.decode(plan_json)

-- 全额退还
for _, p in ipairs(plan) do
  if p.b == 'SUB' then
    redis.call('HINCRBY', wallet, 'sub_used', -(p.h or 0))
  elseif p.b == 'TIMES' then
    redis.call('HINCRBY', wallet, 'times_balance', 1)
  elseif p.b == 'TOKEN' then
    redis.call('HINCRBY', wallet, 'token_balance', (p.h or 0))
  elseif p.b == 'OVERRUN' then
    redis.call('HINCRBY', wallet, 'overrun_used_cent', -(p.cent or 0))
  end
end

redis.call('HSET', resv, 'status', 'RELEASED', 'released', now_ms)
redis.call('HINCRBY', wallet, 'version', 1)

return {1, "RELEASED"}
