"""审批 token:与 C# ``ApprovalTokenVerifier`` 二进制兼容.

格式: base64url(payload) "." base64url(HMAC-SHA256(payload))
payload = tenant|user|dataset|maxRows|expiresUnix|approver|nonce
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def issue(secret: str, tenant_id: int, user_id: int, data_set: str, max_rows: int,
          expires_at: int, approver: str, nonce: str | None = None) -> str:
    nonce = nonce or secrets.token_hex(4)
    payload = f"{tenant_id}|{user_id}|{data_set}|{max_rows}|{expires_at}|{approver}|{nonce}".encode()
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    return _b64e(payload) + "." + _b64e(sig)


@dataclass
class VerifyResult:
    valid: bool
    error: str = ""
    tenant_id: int = 0
    user_id: int = 0
    data_set: str = ""
    max_rows: int = 0
    expires_at: int = 0
    approver: str = ""
    nonce: str = ""


def verify(secret: str, token: str, *, tenant_id: int | None = None, user_id: int | None = None,
           data_set: str | None = None, row_count: int | None = None, now: int | None = None) -> VerifyResult:
    if not token or "." not in token:
        return VerifyResult(False, "format")
    p, s = token.split(".", 1)
    try:
        payload, sig = _b64d(p), _b64d(s)
    except Exception:
        return VerifyResult(False, "base64")
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, sig):
        return VerifyResult(False, "signature")
    parts = payload.decode(errors="replace").split("|")
    if len(parts) < 7:
        return VerifyResult(False, "payload")
    try:
        t, u, ds, mr, exp, approver, nonce = int(parts[0]), int(parts[1]), parts[2], int(parts[3]), int(parts[4]), parts[5], parts[6]
    except ValueError:
        return VerifyResult(False, "payload")
    r = VerifyResult(True, "", t, u, ds, mr, exp, approver, nonce)
    if tenant_id is not None and t != tenant_id:
        return VerifyResult(False, "tenant")
    if user_id is not None and u != user_id:
        return VerifyResult(False, "user")
    if data_set is not None and ds.lower() != data_set.lower():
        return VerifyResult(False, "dataset")
    if row_count is not None and row_count > mr:
        return VerifyResult(False, "rows")
    if exp < (now if now is not None else int(time.time())):
        return VerifyResult(False, "expired")
    return r
