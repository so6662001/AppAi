--[[
  settle.lua — 实际用量结算 (多退少补)
  KEYS:
    [1] wallet:{tid}
    [2] resv:{rid}
  ARGV:
    [1] actual_biz_token   实际消耗 (int)
    [2] now_ms             当前毫秒
    [3] allow_overrun      允许超额补扣 (0/1)
  返回:
    成功: { 1, "SETTLED", diff }
    失败: { 0, err_code }
]]--

local wallet = KEYS[1]
local resv   = KEYS[2]

local actual    = tonumber(ARGV[1])
local now_ms    = tonumber(ARGV[2])
local allow_ovr = tonumber(ARGV[3])

if redis.call('EXISTS', resv) == 0 then
  return {0, "RESV_NOT_FOUND"}
end

local status = redis.call('HGET', resv, 'status')
if status ~= 'HELD' then
  return {0, "RESV_STATE_" .. tostring(status)}
end

local function hgeti(k, f)
  local v = redis.call('HGET', k, f)
  return tonumber(v) or 0
end

local plan_json = redis.call('HGET', resv, 'plan')
local plan = cjson.decode(plan_json)

-- 检查是否次数包覆盖
local has_times = false
for _, p in ipairs(plan) do
  if p.b == 'TIMES' then has_times = true end
end
if has_times then
  redis.call('HSET', resv, 'status', 'SETTLED', 'settled', now_ms, 'actual', actual)
  return {1, "SETTLED", 0}
end

-- 计算预扣总量(扣除 TIMES 项)
local hold_total = 0
for _, p in ipairs(plan) do
  if p.b ~= 'TIMES' then hold_total = hold_total + (p.h or 0) end
end

local diff = actual - hold_total

if diff < 0 then
  -- 多退: 按 plan 逆序退还
  local refund = -diff
  for i = #plan, 1, -1 do
    local p = plan[i]
    if refund <= 0 then break end
    local back = math.min(p.h or 0, refund)
    if back > 0 then
      if p.b == 'SUB' then
        redis.call('HINCRBY', wallet, 'sub_used', -back)
      elseif p.b == 'TOKEN' then
        redis.call('HINCRBY', wallet, 'token_balance', back)
      elseif p.b == 'OVERRUN' then
        local price = hgeti(wallet, 'overrun_price_cent_per_1k')
        if price <= 0 then price = 40 end
        local cent_back = math.ceil(back * price / 1000)
        redis.call('HINCRBY', wallet, 'overrun_used_cent', -cent_back)
      end
      p.h = (p.h or 0) - back
      refund = refund - back
    end
  end
elseif diff > 0 then
  -- 少补: 按 SUB → TOKEN → OVERRUN 再扣
  local need = diff
  -- SUB
  local sub_quota = hgeti(wallet, 'sub_quota')
  local sub_used  = hgeti(wallet, 'sub_used')
  local sub_left  = sub_quota - sub_used
  if sub_left > 0 and need > 0 then
    local take = math.min(sub_left, need)
    redis.call('HINCRBY', wallet, 'sub_used', take)
    table.insert(plan, {b='SUB', h=take, extra=1})
    need = need - take
  end
  -- TOKEN
  if need > 0 then
    local tok = hgeti(wallet, 'token_balance')
    if tok > 0 then
      local take = math.min(tok, need)
      redis.call('HINCRBY', wallet, 'token_balance', -take)
      table.insert(plan, {b='TOKEN', h=take, extra=1})
      need = need - take
    end
  end
  -- OVERRUN
  if need > 0 and allow_ovr == 1 then
    local price = hgeti(wallet, 'overrun_price_cent_per_1k')
    if price <= 0 then price = 40 end
    local cost = math.ceil(need * price / 1000)
    redis.call('HINCRBY', wallet, 'overrun_used_cent', cost)
    table.insert(plan, {b='OVERRUN', h=need, cent=cost, extra=1})
    need = 0
  end
  if need > 0 then
    -- 仍不足, 记入欠款 (一般是配置错误, 不应阻塞业务)
    table.insert(plan, {b='DEBT', h=need, extra=1})
  end
end

redis.call('HSET', resv,
  'status', 'SETTLED',
  'settled', now_ms,
  'actual', actual,
  'plan', cjson.encode(plan)
)
redis.call('HINCRBY', wallet, 'version', 1)

return {1, "SETTLED", diff}
