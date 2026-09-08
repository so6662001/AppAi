--[[
  preauth.lua — 预扣费 (原子, Redis EVAL)
  扣减优先级: SUB → TIMES → TOKEN → OVERRUN
  KEYS:
    [1] wallet:{tid}        Hash
    [2] resv:{rid}          Hash
  ARGV:
    [1] estimate_biz_token   预估业务 token (int)
    [2] need_times_one       是否允许走次数包 (0/1)
    [3] allow_overrun        是否允许超额信用 (0/1)
    [4] now_ms               当前毫秒
    [5] tenant_id
    [6] user_id
    [7] session_id
    [8] message_id
  返回:
    成功: { 1, plan_json }       plan = [{b,h,...}]
    失败: { 0, err_code }
  err_code: INSUFFICIENT / INSUFFICIENT_CREDIT / INVALID_INPUT
]]--

local wallet = KEYS[1]
local resv   = KEYS[2]

local estimate     = tonumber(ARGV[1])
local need_times   = tonumber(ARGV[2])
local allow_over   = tonumber(ARGV[3])
local now_ms       = tonumber(ARGV[4])
local tid          = ARGV[5]
local uid          = ARGV[6]
local sid          = ARGV[7]
local mid          = ARGV[8]

if not estimate or estimate <= 0 then
  return {0, "INVALID_INPUT"}
end

local function hgeti(k, f)
  local v = redis.call('HGET', k, f)
  return tonumber(v) or 0
end

-- 幂等: 相同 message_id 的预扣返回原 reservation
if mid and mid ~= "" then
  local existing = redis.call('GET', "idem:msg:" .. mid)
  if existing then
    local existing_plan = redis.call('HGET', "resv:" .. existing, 'plan')
    return {1, existing_plan or "[]"}
  end
end

local remain = estimate
local plan = {}

-- 1) SUB 订阅周期内额度
local sub_quota = hgeti(wallet, 'sub_quota')
local sub_used  = hgeti(wallet, 'sub_used')
local sub_left  = sub_quota - sub_used
if sub_left > 0 and remain > 0 then
  local take = math.min(sub_left, remain)
  redis.call('HINCRBY', wallet, 'sub_used', take)
  table.insert(plan, {b='SUB', h=take})
  remain = remain - take
end

-- 2) TIMES 次数包 (按"次"扣 1, 整次问答覆盖, 不再继续扣 token)
if need_times == 1 and hgeti(wallet, 'times_balance') > 0 then
  redis.call('HINCRBY', wallet, 'times_balance', -1)
  table.insert(plan, {b='TIMES', h=1, times=1})
  remain = 0
end

-- 3) TOKEN 包余额
if remain > 0 then
  local tok = hgeti(wallet, 'token_balance')
  if tok > 0 then
    local take = math.min(tok, remain)
    redis.call('HINCRBY', wallet, 'token_balance', -take)
    table.insert(plan, {b='TOKEN', h=take})
    remain = remain - take
  end
end

-- 4) OVERRUN 超额信用
if remain > 0 then
  if allow_over == 1 then
    local price = hgeti(wallet, 'overrun_price_cent_per_1k')
    if price <= 0 then price = 40 end
    local limit = hgeti(wallet, 'overrun_limit_cent')
    local used  = hgeti(wallet, 'overrun_used_cent')
    local cost_cent = math.ceil(remain * price / 1000)
    if used + cost_cent > limit then
      -- 回滚已扣
      for _, p in ipairs(plan) do
        if p.b == 'SUB' then
          redis.call('HINCRBY', wallet, 'sub_used', -p.h)
        elseif p.b == 'TIMES' then
          redis.call('HINCRBY', wallet, 'times_balance', 1)
        elseif p.b == 'TOKEN' then
          redis.call('HINCRBY', wallet, 'token_balance', p.h)
        end
      end
      return {0, "INSUFFICIENT_CREDIT"}
    end
    redis.call('HINCRBY', wallet, 'overrun_used_cent', cost_cent)
    table.insert(plan, {b='OVERRUN', h=remain, cent=cost_cent})
    remain = 0
  else
    -- 不允许超额, 回滚
    for _, p in ipairs(plan) do
      if p.b == 'SUB' then
        redis.call('HINCRBY', wallet, 'sub_used', -p.h)
      elseif p.b == 'TIMES' then
        redis.call('HINCRBY', wallet, 'times_balance', 1)
      elseif p.b == 'TOKEN' then
        redis.call('HINCRBY', wallet, 'token_balance', p.h)
      end
    end
    return {0, "INSUFFICIENT"}
  end
end

local plan_json = cjson.encode(plan)
redis.call('HSET', resv,
  'tid', tid, 'uid', uid, 'sid', sid, 'mid', mid,
  'status', 'HELD',
  'plan', plan_json,
  'estimate', estimate,
  'created', now_ms
)
redis.call('PEXPIRE', resv, 180000)            -- 3 分钟 TTL
redis.call('HINCRBY', wallet, 'version', 1)

if mid and mid ~= "" then
  -- 幂等键 10 分钟
  local rid = string.match(resv, "resv:(.+)") or resv
  redis.call('SET', "idem:msg:" .. mid, rid, 'PX', 600000)
end

return {1, plan_json}
