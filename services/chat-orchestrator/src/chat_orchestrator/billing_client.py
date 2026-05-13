"""调用 billing-service 做 preauth/settle/release."""
from __future__ import annotations
import logging
from typing import Optional
import httpx

from .config import settings


log = logging.getLogger("chat.billing")


def preauth(tenant_id: int, user_id: int, session_id: str, message_id: str,
            estimate: int) -> Optional[str]:
    """返回 reservation_id, 不可达时返回 None (允许继续, 由 sweeper 兜底)."""
    try:
        r = httpx.post(f"{settings.billing_url}/billing/preauth", json={
            "tenant_id": tenant_id, "user_id": user_id,
            "session_id": session_id, "message_id": message_id,
            "estimate": estimate,
        }, timeout=5)
        if r.status_code == 200:
            return r.json().get("reservationId")
    except Exception as e:
        log.debug("preauth unavailable: %s", e)
    return None


def settle(tenant_id: int, reservation_id: str, actual: int,
           model_name: str, input_tokens: int, output_tokens: int,
           query_rows: int, cache_hit: bool):
    if not reservation_id:
        return
    try:
        httpx.post(f"{settings.billing_url}/billing/settle", json={
            "tenant_id": tenant_id, "reservation_id": reservation_id,
            "actual": actual, "model_name": model_name,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "query_rows": query_rows, "cache_hit": cache_hit,
        }, timeout=5)
    except Exception as e:
        log.debug("settle unavailable: %s", e)


def release(tenant_id: int, reservation_id: str):
    if not reservation_id: return
    try:
        httpx.post(f"{settings.billing_url}/billing/release", json={
            "tenant_id": tenant_id, "reservation_id": reservation_id,
        }, timeout=5)
    except Exception: pass
