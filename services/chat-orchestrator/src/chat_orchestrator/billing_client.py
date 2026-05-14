"""调用 billing-service 做 preauth/settle/release.

可靠性:
  - 失败时写本地 outbox 文件 (file-based), 后台扫描重试; 避免账务长期不一致
  - 所有调用记录到 outbox, 即便成功也保留 24h 便于对账
  - HTTP 4xx (业务错误) 与 5xx (服务错误) 区分: 4xx 不重试, 5xx 进 outbox
"""
from __future__ import annotations
import json
import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional
import httpx

from .config import settings


log = logging.getLogger("chat.billing")
# 使用 tempfile.gettempdir() 而非硬编码 /tmp, 兼容 Windows 与不同部署环境
import tempfile
_OUTBOX_DIR = Path(os.environ.get("BILLING_OUTBOX_DIR",
                                   str(Path(tempfile.gettempdir()) / "chat-billing-outbox")))
_OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()


def _outbox_write(kind: str, payload: dict):
    """失败的请求记录到 outbox, 待重试."""
    try:
        with _lock:
            fname = _OUTBOX_DIR / f"{int(time.time()*1000)}_{kind}.json"
            fname.write_text(json.dumps({
                "kind": kind, "payload": payload, "ts": time.time(),
                "retries": 0,
            }, ensure_ascii=False))
            log.warning("billing %s queued to outbox: %s", kind, fname.name)
    except Exception:
        log.exception("outbox write failed (fatal!)")


def preauth(tenant_id: int, user_id: int, session_id: str, message_id: str,
            estimate: int) -> Optional[str]:
    """返回 reservation_id, 不可达时返回 None (允许继续, 由 sweeper 兜底)."""
    payload = {
        "tenant_id": tenant_id, "user_id": user_id,
        "session_id": session_id, "message_id": message_id,
        "estimate": estimate,
    }
    try:
        r = httpx.post(f"{settings.billing_url}/billing/preauth",
                       json=payload, timeout=5)
        if r.status_code == 200:
            return r.json().get("reservationId")
        elif r.status_code == 402:
            # 余额不足 - 业务错误, 不重试
            log.warning("preauth INSUFFICIENT for tenant=%s user=%s", tenant_id, user_id)
            return None
        else:
            log.error("preauth http %s: %s", r.status_code, r.text[:200])
            _outbox_write("preauth", payload)
            return None
    except Exception as e:
        log.warning("preauth unreachable: %s", e)
        _outbox_write("preauth", payload)
        return None


def settle(tenant_id: int, reservation_id: str, actual: int,
           model_name: str, input_tokens: int, output_tokens: int,
           query_rows: int, cache_hit: bool) -> bool:
    """返回 True 表示成功结算; False 表示已入 outbox 等待重试."""
    if not reservation_id:
        log.debug("settle skipped: no reservation_id")
        return False
    payload = {
        "tenant_id": tenant_id, "reservation_id": reservation_id,
        "actual": actual, "model_name": model_name,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "query_rows": query_rows, "cache_hit": cache_hit,
    }
    try:
        r = httpx.post(f"{settings.billing_url}/billing/settle",
                       json=payload, timeout=5)
        if r.status_code == 200:
            return True
        log.error("settle http %s: %s", r.status_code, r.text[:200])
        _outbox_write("settle", payload)
        return False
    except Exception as e:
        log.warning("settle unreachable: %s", e)
        _outbox_write("settle", payload)
        return False


def release(tenant_id: int, reservation_id: str) -> bool:
    if not reservation_id:
        return True
    payload = {"tenant_id": tenant_id, "reservation_id": reservation_id}
    try:
        r = httpx.post(f"{settings.billing_url}/billing/release",
                       json=payload, timeout=5)
        if r.status_code == 200:
            return True
        log.warning("release http %s: %s", r.status_code, r.text[:200])
        _outbox_write("release", payload)
        return False
    except Exception as e:
        log.warning("release unreachable: %s", e)
        _outbox_write("release", payload)
        return False


# ============ Outbox 后台重试 ============

def _process_outbox():
    """逐个重试 outbox 中的失败请求 (FIFO). 成功删除文件, 失败则增加 retries."""
    files = sorted(_OUTBOX_DIR.glob("*.json"))
    for f in files[:50]:
        try:
            data = json.loads(f.read_text())
            kind = data["kind"]; payload = data["payload"]
            retries = data.get("retries", 0)
            if retries >= 5:
                # 5 次失败 → 移到 dead-letter
                dead = _OUTBOX_DIR / "dead" / f.name
                dead.parent.mkdir(exist_ok=True)
                f.rename(dead)
                log.error("billing outbox dead-letter: %s", f.name)
                continue
            url = f"{settings.billing_url}/billing/{kind}"
            try:
                r = httpx.post(url, json=payload, timeout=5)
                if r.status_code == 200:
                    f.unlink()
                    log.info("billing outbox retry success: %s", f.name)
                else:
                    data["retries"] = retries + 1
                    f.write_text(json.dumps(data, ensure_ascii=False))
            except Exception:
                data["retries"] = retries + 1
                f.write_text(json.dumps(data, ensure_ascii=False))
        except Exception:
            log.exception("outbox file corrupted: %s", f.name)


def start_outbox_worker(interval: int = 30):
    """后台线程定时重试."""
    def loop():
        while True:
            try: _process_outbox()
            except Exception: log.exception("outbox loop")
            time.sleep(interval)
    t = threading.Thread(target=loop, daemon=True, name="billing-outbox")
    t.start()
    log.info("billing outbox worker started, interval=%ss", interval)
