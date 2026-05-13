"""计费 Lua 脚本集成测试。

需要本地有 Redis (默认 localhost:6379)。
执行: pytest -v
"""
from __future__ import annotations
import os
import time
import json
import uuid
from pathlib import Path

import pytest
import redis


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def r():
    # 优先连真实 Redis, 没有则用 fakeredis (支持 Lua)
    try:
        client = redis.Redis(
            host=os.environ.get("REDIS_HOST", "localhost"),
            port=int(os.environ.get("REDIS_PORT", 6379)),
            decode_responses=True, socket_connect_timeout=1,
        )
        client.ping()
        return client
    except Exception:
        try:
            import fakeredis
            return fakeredis.FakeRedis(decode_responses=True)
        except Exception:
            pytest.skip("无 Redis 也无 fakeredis[lua]")


@pytest.fixture(scope="session")
def scripts(r):
    return {
        "preauth": r.script_load((ROOT / "preauth.lua").read_text()),
        "settle":  r.script_load((ROOT / "settle.lua").read_text()),
        "release": r.script_load((ROOT / "release.lua").read_text()),
        "refund":  r.script_load((ROOT / "refund.lua").read_text()),
    }


@pytest.fixture
def fresh_wallet(r):
    tid = 9000 + int(time.time() * 1000) % 1000
    wallet_key = f"wallet:{tid}"
    r.delete(wallet_key)
    r.hset(wallet_key, mapping={
        "sub_quota": 100000,
        "sub_used":  0,
        "times_balance": 5,
        "token_balance": 50000,
        "overrun_limit_cent":     20000,    # 200 元
        "overrun_used_cent":      0,
        "overrun_price_cent_per_1k": 40,
        "version": 0,
    })
    yield tid, wallet_key
    r.delete(wallet_key)


def _new_resv():
    rid = uuid.uuid4().hex
    return rid, f"resv:{rid}"


# =================== 预扣测试 ===================

def test_preauth_sub_only(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    ok, plan = r.evalsha(scripts["preauth"], 2, wkey, rkey,
                         2000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m1")
    assert ok == 1
    plan = json.loads(plan)
    assert plan[0]["b"] == "SUB"
    assert plan[0]["h"] == 2000
    assert int(r.hget(wkey, "sub_used")) == 2000


def test_preauth_overflow_to_token(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    # 申请超过 sub_quota 的额度, 会流到 token
    ok, plan = r.evalsha(scripts["preauth"], 2, wkey, rkey,
                         120000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m2")
    assert ok == 1
    plan = json.loads(plan)
    buckets = [p["b"] for p in plan]
    assert "SUB" in buckets and "TOKEN" in buckets
    assert int(r.hget(wkey, "sub_used")) == 100000
    assert int(r.hget(wkey, "token_balance")) == 50000 - 20000


def test_preauth_insufficient(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    # 申请大于所有余额
    ok, code = r.evalsha(scripts["preauth"], 2, wkey, rkey,
                         9999999, 0, 0, int(time.time()*1000), tid, 1, "s1", "m3")
    assert ok == 0
    assert code == "INSUFFICIENT"
    # 钱包应未变
    assert int(r.hget(wkey, "sub_used")) == 0
    assert int(r.hget(wkey, "token_balance")) == 50000


def test_preauth_times_pack_takes_priority(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    # need_times=1, 用次数包消费一次
    ok, plan = r.evalsha(scripts["preauth"], 2, wkey, rkey,
                         5000, 1, 0, int(time.time()*1000), tid, 1, "s1", "m4")
    assert ok == 1
    plan = json.loads(plan)
    assert any(p["b"] == "TIMES" for p in plan)
    assert int(r.hget(wkey, "times_balance")) == 4


def test_preauth_idempotent(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid1, rkey1 = _new_resv()
    msg_id = "dup-msg-001"
    ok1, plan1 = r.evalsha(scripts["preauth"], 2, wkey, rkey1,
                           2000, 0, 0, int(time.time()*1000), tid, 1, "s1", msg_id)
    assert ok1 == 1
    used_first = int(r.hget(wkey, "sub_used"))
    # 再来一次相同 msg_id
    rid2, rkey2 = _new_resv()
    ok2, plan2 = r.evalsha(scripts["preauth"], 2, wkey, rkey2,
                           2000, 0, 0, int(time.time()*1000), tid, 1, "s1", msg_id)
    assert ok2 == 1
    # 不应再次扣减
    assert int(r.hget(wkey, "sub_used")) == used_first


def test_preauth_overrun(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    # 把 sub + token 用光
    r.hset(wkey, "sub_used", 100000)
    r.hset(wkey, "token_balance", 0)
    # 申请 5000 token, 允许 overrun
    ok, plan = r.evalsha(scripts["preauth"], 2, wkey, rkey,
                         5000, 0, 1, int(time.time()*1000), tid, 1, "s1", "m_or")
    assert ok == 1
    plan = json.loads(plan)
    assert any(p["b"] == "OVERRUN" for p in plan)
    assert int(r.hget(wkey, "overrun_used_cent")) > 0


# =================== 结算测试 ===================

def test_settle_refund(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    r.evalsha(scripts["preauth"], 2, wkey, rkey,
              5000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m5")
    used_before = int(r.hget(wkey, "sub_used"))
    # 实际只用 3000
    ok, msg, diff = r.evalsha(scripts["settle"], 2, wkey, rkey,
                              3000, int(time.time()*1000), 0)
    assert ok == 1
    assert msg == "SETTLED"
    assert diff == -2000
    # 退回 2000 给 sub
    assert int(r.hget(wkey, "sub_used")) == used_before - 2000


def test_settle_extra_deduct(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    r.evalsha(scripts["preauth"], 2, wkey, rkey,
              2000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m6")
    # 实际用了 3000, 多扣 1000
    ok, msg, diff = r.evalsha(scripts["settle"], 2, wkey, rkey,
                              3000, int(time.time()*1000), 0)
    assert ok == 1
    assert diff == 1000
    # sub_used = 2000(原扣) + 1000(补扣) = 3000
    assert int(r.hget(wkey, "sub_used")) == 3000


def test_settle_times_pack_no_diff(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    r.evalsha(scripts["preauth"], 2, wkey, rkey,
              5000, 1, 0, int(time.time()*1000), tid, 1, "s1", "m7")
    times_after = int(r.hget(wkey, "times_balance"))
    ok, msg, diff = r.evalsha(scripts["settle"], 2, wkey, rkey,
                              4000, int(time.time()*1000), 0)
    assert ok == 1 and diff == 0
    # 次数包不再多扣
    assert int(r.hget(wkey, "times_balance")) == times_after


# =================== 释放测试 ===================

def test_release_full_refund(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    r.evalsha(scripts["preauth"], 2, wkey, rkey,
              5000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m8")
    used_pre = int(r.hget(wkey, "sub_used"))
    ok, msg = r.evalsha(scripts["release"], 2, wkey, rkey, int(time.time()*1000))
    assert ok == 1 and msg == "RELEASED"
    assert int(r.hget(wkey, "sub_used")) == used_pre - 5000


def test_release_after_settle_fails(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    rid, rkey = _new_resv()
    r.evalsha(scripts["preauth"], 2, wkey, rkey,
              5000, 0, 0, int(time.time()*1000), tid, 1, "s1", "m9")
    r.evalsha(scripts["settle"], 2, wkey, rkey,
              5000, int(time.time()*1000), 0)
    ok, code = r.evalsha(scripts["release"], 2, wkey, rkey, int(time.time()*1000))
    assert ok == 0 and code == "ALREADY_SETTLED"


# =================== 退款测试 ===================

def test_refund_token(r, scripts, fresh_wallet):
    tid, wkey = fresh_wallet
    pre = int(r.hget(wkey, "token_balance"))
    ok, msg = r.evalsha(scripts["refund"], 1, wkey, "TOKEN", 10000,
                       int(time.time()*1000), "order-001")
    assert ok == 1
    assert int(r.hget(wkey, "token_balance")) == pre + 10000
