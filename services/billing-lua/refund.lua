--[[
  refund.lua — 退款/调账(售后)
  KEYS: [1] wallet:{tid}
  ARGV:
    [1] account     SUB / TIMES / TOKEN / OVERRUN
    [2] amount      正数 (退还方向: 余额增加, 已用减少)
    [3] now_ms
    [4] ref_id      关联订单/工单 id
  返回: { 1, "REFUNDED" }
]]--

local wallet  = KEYS[1]
local account = ARGV[1]
local amount  = tonumber(ARGV[2])
local now_ms  = tonumber(ARGV[3])
local ref_id  = ARGV[4]

if not amount or amount <= 0 then
  return {0, "INVALID_AMOUNT"}
end

if account == 'SUB' then
  redis.call('HINCRBY', wallet, 'sub_used', -amount)
elseif account == 'TIMES' then
  redis.call('HINCRBY', wallet, 'times_balance', amount)
elseif account == 'TOKEN' then
  redis.call('HINCRBY', wallet, 'token_balance', amount)
elseif account == 'OVERRUN' then
  redis.call('HINCRBY', wallet, 'overrun_used_cent', -amount)
else
  return {0, "UNKNOWN_ACCOUNT"}
end

redis.call('HINCRBY', wallet, 'version', 1)

-- 写一条审计记录到 List(由消费者搬运到 MySQL ledger)
local audit = cjson.encode({
  ts = now_ms, account = account, amount = amount,
  ref_id = ref_id, kind = 'REFUND'
})
redis.call('LPUSH', 'billing:audit:queue', audit)

return {1, "REFUNDED"}
