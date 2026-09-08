# 计费 Redis Lua 脚本

钱包扣减的原子操作集。所有脚本在 Redis 单实例上保证原子性。

## 脚本一览

| 文件 | 作用 | KEYS | ARGV |
|------|------|------|------|
| `preauth.lua` | 预扣占用（按 SUB→TIMES→TOKEN→OVERRUN 顺序） | wallet, resv | estimate / need_times / allow_overrun / now_ms / tid / uid / sid / mid |
| `settle.lua` | 结算多退少补 | wallet, resv | actual / now_ms / allow_overrun |
| `release.lua` | 释放预扣（用户中断/扫描超时） | wallet, resv | now_ms |
| `refund.lua` | 售后退款/调账 | wallet | account / amount / now_ms / ref_id |

## 钱包数据结构（Redis Hash）

```
wallet:{tid}
  sub_quota                BIGINT     本周期订阅额度
  sub_used                 BIGINT     本周期已用
  times_balance            INT        次数包余额
  token_balance            BIGINT     业务 token 余额
  overrun_limit_cent       INT        允许的超额信用 (分)
  overrun_used_cent        INT        已使用的超额 (分)
  overrun_price_cent_per_1k INT       超额单价 (分/千 biz token)
  version                  BIGINT     乐观锁
```

## 预扣占用

```
resv:{rid}
  tid, uid, sid, mid
  status      HELD / SETTLED / RELEASED
  plan        JSON: [{b: SUB, h: 2000}, {b: TOKEN, h: 500}, ...]
  estimate    BIGINT
  created     ms
  PEXPIRE 180000ms
```

## 幂等

`preauth.lua` 在收到非空 `message_id` 时写 `idem:msg:{mid} = {rid}`（PEXPIRE 600s），重复调用直接返回原计划，**钱包不会二次扣减**。

## Java 使用示例

```java
// 启动时加载脚本拿到 sha1
String preauthSha = jedis.scriptLoad(readResource("preauth.lua"));

// 调用预扣
List<String> resp = (List<String>) jedis.evalsha(preauthSha, 2,
    "wallet:" + tenantId, "resv:" + reservationId,
    String.valueOf(estimate), "0", "1",  // estimate, need_times, allow_overrun
    String.valueOf(System.currentTimeMillis()),
    String.valueOf(tenantId), String.valueOf(userId),
    sessionId, messageId);

if ("1".equals(resp.get(0))) {
    String planJson = resp.get(1);   // 记录到数据库 outbox
} else {
    String errCode = resp.get(1);    // INSUFFICIENT / INSUFFICIENT_CREDIT
    throw new BillingException(errCode);
}
```

## 测试

```bash
# 真实 Redis (推荐)
redis-server &
cd services/billing-lua
pytest -v

# 或: 用 fakeredis 跑(免装 Redis)
pip install 'fakeredis[lua]'
pytest -v
```

测试覆盖：
- 预扣 SUB / SUB→TOKEN 流转 / 不足回滚 / 次数包覆盖 / 幂等 / 超额信用
- 结算多退 / 少补 / 次数包不调整
- 释放全额退还 / 已结算不可再释放
- 退款余额变更

12 个用例全绿。
