"""存储层:内存实现(测试 / 单机)+ MySQL 实现(生产, 表见 ddl/22_client_guard.sql)."""
from __future__ import annotations
import json
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol

from .models import ExportRequestRecord, GuardEvent, GuardPolicy, SessionLinkRecord

log = logging.getLogger("client-guard.store")


class Store(Protocol):
    def put_link(self, r: SessionLinkRecord) -> None: ...
    def get_link(self, link_id: str) -> Optional[SessionLinkRecord]: ...
    def find_link_by_nonce(self, tenant_id: int, user_id: int, nonce: str) -> Optional[SessionLinkRecord]: ...
    def find_link_by_machine(self, tenant_id: int, user_id: int, machine_name: str, since: datetime) -> Optional[SessionLinkRecord]: ...
    def has_launcher_activity(self, tenant_id: int, user_id: int, since: datetime) -> bool: ...
    def get_policy(self, tenant_id: int) -> Optional[GuardPolicy]: ...
    def put_policy(self, tenant_id: int, policy: GuardPolicy, updated_by: int | None) -> None: ...
    def add_events(self, events: list[GuardEvent]) -> int: ...
    def recent_events(self, tenant_id: int, user_id: int, since: datetime) -> list[GuardEvent]: ...
    def export_usage(self, tenant_id: int, user_id: int, now: datetime) -> tuple[int, int]: ...
    def record_export(self, tenant_id: int, user_id: int, rows: int, now: datetime) -> None: ...
    def put_request(self, r: ExportRequestRecord) -> None: ...
    def get_request(self, request_id: str) -> Optional[ExportRequestRecord]: ...
    def list_requests(self, tenant_id: int, status: str | None, limit: int) -> list[ExportRequestRecord]: ...
    def mark_token_used(self, nonce: str) -> bool: ...
    def touch_device(self, tenant_id: int, user_id: int, device_id: str, server_score: float, now: datetime) -> None: ...
    def get_directive(self, tenant_id: int, user_id: int, device_id: str, now: datetime) -> tuple[str, str]: ...
    def set_directive(self, tenant_id: int, user_id: int, device_id: str, directive: str, reason: str, until: datetime | None, trusted: bool | None) -> None: ...
    def is_trusted(self, tenant_id: int, user_id: int, device_id: str) -> bool: ...


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._policies: dict[int, GuardPolicy] = {}
        self._events: list[GuardEvent] = []
        self._event_ids: set[str] = set()
        self._exports: dict[tuple[int, int], list[tuple[datetime, int]]] = defaultdict(list)
        self._requests: dict[str, ExportRequestRecord] = {}
        self._used_nonces: set[str] = set()
        self._devices: dict[tuple[int, int, str], dict] = {}
        self._links: dict[str, SessionLinkRecord] = {}

    # ---- 双端绑定 ----
    def put_link(self, r):
        with self._lock:
            self._links[r.link_id] = r
            if len(self._links) > 50_000:
                for k in sorted(self._links, key=lambda k: self._links[k].created_at)[:10_000]:
                    del self._links[k]

    def get_link(self, link_id):
        with self._lock:
            return self._links.get(link_id)

    def find_link_by_nonce(self, tenant_id, user_id, nonce):
        with self._lock:
            for r in self._links.values():
                if r.tenant_id == tenant_id and r.user_id == user_id and r.ticket_nonce == nonce:
                    return r
            return None

    def find_link_by_machine(self, tenant_id, user_id, machine_name, since):
        with self._lock:
            cands = [r for r in self._links.values()
                     if r.tenant_id == tenant_id and r.user_id == user_id and r.machine_name.lower() == machine_name.lower()
                     and _utc(r.created_at) >= since]
            cands.sort(key=lambda r: r.created_at, reverse=True)
            return cands[0] if cands else None

    def has_launcher_activity(self, tenant_id, user_id, since):
        with self._lock:
            return any(e.tenant_id == tenant_id and e.user_id == user_id and e.side == "launcher" and _utc(e.at) >= since
                       for e in self._events)

    def get_policy(self, tenant_id):
        with self._lock:
            return self._policies.get(tenant_id)

    def put_policy(self, tenant_id, policy, updated_by):
        with self._lock:
            self._policies[tenant_id] = policy

    def add_events(self, events):
        with self._lock:
            n = 0
            for e in events:
                if e.event_id in self._event_ids:
                    continue
                self._event_ids.add(e.event_id)
                self._events.append(e)
                n += 1
            if len(self._events) > 200_000:
                self._events = self._events[-100_000:]
                self._event_ids = {e.event_id for e in self._events}
            return n

    def recent_events(self, tenant_id, user_id, since):
        with self._lock:
            return [e for e in self._events if e.tenant_id == tenant_id and e.user_id == user_id and _utc(e.at) >= since]

    def export_usage(self, tenant_id, user_id, now):
        with self._lock:
            hist = self._exports.get((tenant_id, user_id), [])
            hour = sum(1 for at, _ in hist if now - at <= timedelta(hours=1))
            day = sum(r for at, r in hist if _local_date(at) == _local_date(now))
            return hour, day

    def record_export(self, tenant_id, user_id, rows, now):
        with self._lock:
            lst = self._exports[(tenant_id, user_id)]
            lst.append((now, rows))
            cutoff = now - timedelta(days=2)
            lst[:] = [x for x in lst if x[0] >= cutoff]

    def put_request(self, r):
        with self._lock:
            self._requests[r.request_id] = r

    def get_request(self, request_id):
        with self._lock:
            return self._requests.get(request_id)

    def list_requests(self, tenant_id, status, limit):
        with self._lock:
            rs = [r for r in self._requests.values() if r.tenant_id == tenant_id and (status is None or r.status == status)]
            rs.sort(key=lambda r: r.created_at, reverse=True)
            return rs[:limit]

    def mark_token_used(self, nonce):
        with self._lock:
            if nonce in self._used_nonces:
                return False
            self._used_nonces.add(nonce)
            return True

    def touch_device(self, tenant_id, user_id, device_id, server_score, now):
        with self._lock:
            d = self._devices.setdefault((tenant_id, user_id, device_id), {"directive": "none", "reason": "", "until": None, "trusted": False})
            d["last_seen"] = now
            d["server_score"] = server_score

    def get_directive(self, tenant_id, user_id, device_id, now):
        with self._lock:
            d = self._devices.get((tenant_id, user_id, device_id))
            if not d or d["directive"] == "none":
                return "none", ""
            if d["until"] and d["until"] < now:
                d["directive"] = "none"
                return "none", ""
            return d["directive"], d["reason"]

    def set_directive(self, tenant_id, user_id, device_id, directive, reason, until, trusted):
        with self._lock:
            d = self._devices.setdefault((tenant_id, user_id, device_id), {"directive": "none", "reason": "", "until": None, "trusted": False})
            d.update(directive=directive, reason=reason, until=until)
            if trusted is not None:
                d["trusted"] = trusted

    def is_trusted(self, tenant_id, user_id, device_id):
        with self._lock:
            d = self._devices.get((tenant_id, user_id, device_id))
            return bool(d and d.get("trusted"))


class MySqlStore:
    """基于 SQLAlchemy Core 的 MySQL 实现(只在配置 DB_URL_GOV 时启用)."""

    def __init__(self, url: str) -> None:
        from sqlalchemy import create_engine
        self.engine = create_engine(url, pool_pre_ping=True, pool_recycle=1800)

    def _exec(self, sql: str, **params):
        from sqlalchemy import text
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params)

    def get_policy(self, tenant_id):
        row = self._exec("SELECT policy_json, version FROM client_guard_policy WHERE tenant_id=:t", t=tenant_id).first()
        if not row:
            return None
        data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        data["version"] = row[1]
        return GuardPolicy.model_validate(data)

    def put_policy(self, tenant_id, policy, updated_by):
        self._exec(
            "INSERT INTO client_guard_policy(tenant_id, version, policy_json, updated_by) VALUES(:t,:v,:j,:u) "
            "ON DUPLICATE KEY UPDATE version=:v, policy_json=:j, updated_by=:u",
            t=tenant_id, v=policy.version, j=policy.model_dump_json(), u=updated_by)

    def add_events(self, events):
        n = 0
        for e in events:
            try:
                self._exec(
                    "INSERT IGNORE INTO client_guard_event(event_id,tenant_id,user_id,device_id,session_id,side,link_id,client_name,event_at,event_type,"
                    "signal_kind,weight,client_score,client_level,detail,breakdown_json,client_version,os) VALUES("
                    ":eid,:t,:u,:d,:s,:side,:lk,:cn,:at,:ty,:k,:w,:sc,:lv,:de,:bd,:cv,:os)",
                    eid=e.event_id, t=e.tenant_id, u=e.user_id, d=e.device_id, s=e.session_id, side=e.side[:16], lk=e.link_id,
                    cn=(e.client_name or "")[:64] or None, at=_utc(e.at).replace(tzinfo=None),
                    ty=e.type, k=e.kind, w=e.weight, sc=e.score, lv=e.level, de=(e.detail or "")[:1024],
                    bd=json.dumps(e.breakdown) if e.breakdown else None, cv=e.client_version, os=e.os[:128])
                n += 1
            except Exception as ex:  # noqa: BLE001
                log.warning("event insert failed: %s", ex)
        return n

    def recent_events(self, tenant_id, user_id, since):
        rows = self._exec(
            "SELECT event_id,tenant_id,user_id,device_id,session_id,event_at,event_type,signal_kind,weight,client_score,client_level,detail,"
            "side,link_id,client_name "
            "FROM client_guard_event WHERE tenant_id=:t AND user_id=:u AND event_at>=:s ORDER BY event_at",
            t=tenant_id, u=user_id, s=since.replace(tzinfo=None)).all()
        return [GuardEvent(event_id=r[0], tenant_id=r[1], user_id=r[2], device_id=r[3] or "", session_id=r[4] or "",
                           at=r[5].replace(tzinfo=timezone.utc), type=r[6], kind=r[7], weight=r[8], score=float(r[9] or 0),
                           level=r[10], detail=r[11], side=r[12] or "local", link_id=r[13], client_name=r[14]) for r in rows]

    # ---- 双端绑定 ----
    _LINK_COLS = ("link_id,tenant_id,user_id,launcher_device_id,machine_name,ticket_nonce,ticket_expires_at,local_score,status,"
                  "remote_device_id,client_name,client_address,created_at,bound_at")

    def put_link(self, r):
        self._exec(
            f"INSERT INTO client_guard_session_link({self._LINK_COLS}) VALUES(:lid,:t,:u,:ld,:mn,:nonce,:texp,:ls,:st,:rd,:cn,:ca,:cr,:ba) "
            "ON DUPLICATE KEY UPDATE status=:st, remote_device_id=:rd, client_name=:cn, client_address=:ca, bound_at=:ba",
            lid=r.link_id, t=r.tenant_id, u=r.user_id, ld=r.launcher_device_id, mn=r.machine_name[:64], nonce=r.ticket_nonce,
            texp=datetime.fromtimestamp(r.ticket_expires_at, tz=timezone.utc).replace(tzinfo=None) if r.ticket_expires_at else None,
            ls=r.local_score, st=r.status, rd=r.remote_device_id, cn=(r.client_name or "")[:64] or None, ca=(r.client_address or "")[:64] or None,
            cr=_utc(r.created_at).replace(tzinfo=None), ba=_utc(r.bound_at).replace(tzinfo=None) if r.bound_at else None)

    def _row_to_link(self, r) -> SessionLinkRecord:
        return SessionLinkRecord(
            link_id=r[0], tenant_id=r[1], user_id=r[2], launcher_device_id=r[3], machine_name=r[4] or "", ticket_nonce=r[5] or "",
            ticket_expires_at=int(r[6].replace(tzinfo=timezone.utc).timestamp()) if r[6] else 0, local_score=float(r[7] or 0),
            status=r[8], remote_device_id=r[9], client_name=r[10], client_address=r[11],
            created_at=r[12].replace(tzinfo=timezone.utc), bound_at=r[13].replace(tzinfo=timezone.utc) if r[13] else None)

    def get_link(self, link_id):
        r = self._exec(f"SELECT {self._LINK_COLS} FROM client_guard_session_link WHERE link_id=:l", l=link_id).first()
        return self._row_to_link(r) if r else None

    def find_link_by_nonce(self, tenant_id, user_id, nonce):
        r = self._exec(f"SELECT {self._LINK_COLS} FROM client_guard_session_link WHERE tenant_id=:t AND user_id=:u AND ticket_nonce=:n",
                       t=tenant_id, u=user_id, n=nonce).first()
        return self._row_to_link(r) if r else None

    def find_link_by_machine(self, tenant_id, user_id, machine_name, since):
        r = self._exec(
            f"SELECT {self._LINK_COLS} FROM client_guard_session_link WHERE tenant_id=:t AND user_id=:u AND LOWER(machine_name)=:m "
            "AND created_at>=:s ORDER BY created_at DESC LIMIT 1",
            t=tenant_id, u=user_id, m=machine_name.lower(), s=since.replace(tzinfo=None)).first()
        return self._row_to_link(r) if r else None

    def has_launcher_activity(self, tenant_id, user_id, since):
        return bool(self._exec(
            "SELECT 1 FROM client_guard_event WHERE tenant_id=:t AND user_id=:u AND side='launcher' AND event_at>=:s LIMIT 1",
            t=tenant_id, u=user_id, s=since.replace(tzinfo=None)).first())

    def export_usage(self, tenant_id, user_id, now):
        day = self._exec("SELECT row_total FROM client_guard_export_ledger WHERE tenant_id=:t AND user_id=:u AND ledger_date=:d",
                         t=tenant_id, u=user_id, d=_local_date(now)).scalar() or 0
        hour = self._exec("SELECT COUNT(*) FROM client_guard_event WHERE tenant_id=:t AND user_id=:u AND event_type='export' AND event_at>=:s",
                          t=tenant_id, u=user_id, s=(now - timedelta(hours=1)).replace(tzinfo=None)).scalar() or 0
        return int(hour), int(day)

    def record_export(self, tenant_id, user_id, rows, now):
        self._exec(
            "INSERT INTO client_guard_export_ledger(tenant_id,user_id,ledger_date,export_count,row_total,last_export_at) VALUES(:t,:u,:d,1,:r,:n) "
            "ON DUPLICATE KEY UPDATE export_count=export_count+1, row_total=row_total+:r, last_export_at=:n",
            t=tenant_id, u=user_id, d=_local_date(now), r=rows, n=now.replace(tzinfo=None))

    def put_request(self, r):
        self._exec(
            "INSERT INTO client_guard_export_request(request_id,tenant_id,user_id,device_id,data_set,row_count,risk_score,reason,status,"
            "approver_id,approver_name,approve_note,token,token_expires_at,created_at,decided_at) VALUES("
            ":rid,:t,:u,:d,:ds,:rc,:rs,:re,:st,:aid,:an,:note,:tok,:texp,:ca,:da) "
            "ON DUPLICATE KEY UPDATE status=:st, approver_id=:aid, approver_name=:an, approve_note=:note, token=:tok, token_expires_at=:texp, decided_at=:da",
            rid=r.request_id, t=r.tenant_id, u=r.user_id, d=r.device_id, ds=r.data_set, rc=r.row_count, rs=r.risk_score, re=r.reason[:255],
            st=r.status, aid=r.approver_id, an=r.approver_name, note=(r.approve_note or "")[:255], tok=r.token,
            texp=datetime.fromtimestamp(r.token_expires_at, tz=timezone.utc).replace(tzinfo=None) if r.token_expires_at else None,
            ca=_utc(r.created_at).replace(tzinfo=None), da=_utc(r.decided_at).replace(tzinfo=None) if r.decided_at else None)

    def _row_to_request(self, r) -> ExportRequestRecord:
        return ExportRequestRecord(
            request_id=r[0], tenant_id=r[1], user_id=r[2], device_id=r[3] or "", data_set=r[4], row_count=r[5],
            risk_score=float(r[6] or 0), reason=r[7] or "", status=r[8], approver_id=r[9], approver_name=r[10], approve_note=r[11],
            token=r[12], token_expires_at=int(r[13].replace(tzinfo=timezone.utc).timestamp()) if r[13] else None,
            created_at=r[14].replace(tzinfo=timezone.utc), decided_at=r[15].replace(tzinfo=timezone.utc) if r[15] else None)

    _REQ_COLS = ("request_id,tenant_id,user_id,device_id,data_set,row_count,risk_score,reason,status,approver_id,approver_name,"
                 "approve_note,token,token_expires_at,created_at,decided_at")

    def get_request(self, request_id):
        r = self._exec(f"SELECT {self._REQ_COLS} FROM client_guard_export_request WHERE request_id=:r", r=request_id).first()
        return self._row_to_request(r) if r else None

    def list_requests(self, tenant_id, status, limit):
        sql = f"SELECT {self._REQ_COLS} FROM client_guard_export_request WHERE tenant_id=:t"
        params = {"t": tenant_id, "l": limit}
        if status:
            sql += " AND status=:s"
            params["s"] = status
        sql += " ORDER BY created_at DESC LIMIT :l"
        return [self._row_to_request(r) for r in self._exec(sql, **params).all()]

    def mark_token_used(self, nonce):
        res = self._exec("UPDATE client_guard_export_request SET status='used', used_at=NOW() WHERE token LIKE :p AND status='approved'",
                         p=f"%{nonce}%")
        return (res.rowcount or 0) > 0

    def touch_device(self, tenant_id, user_id, device_id, server_score, now):
        self._exec(
            "INSERT INTO client_guard_device(tenant_id,user_id,device_id,server_score,last_seen_at) VALUES(:t,:u,:d,:s,:n) "
            "ON DUPLICATE KEY UPDATE server_score=:s, last_seen_at=:n",
            t=tenant_id, u=user_id, d=device_id, s=server_score, n=now.replace(tzinfo=None))

    def get_directive(self, tenant_id, user_id, device_id, now):
        r = self._exec("SELECT directive, directive_reason, directive_until FROM client_guard_device WHERE tenant_id=:t AND user_id=:u AND device_id=:d",
                       t=tenant_id, u=user_id, d=device_id).first()
        if not r or r[0] == "none":
            return "none", ""
        if r[2] and r[2].replace(tzinfo=timezone.utc) < now:
            return "none", ""
        return r[0], r[1] or ""

    def set_directive(self, tenant_id, user_id, device_id, directive, reason, until, trusted):
        self._exec(
            "INSERT INTO client_guard_device(tenant_id,user_id,device_id,directive,directive_reason,directive_until,trusted) VALUES(:t,:u,:d,:dir,:re,:un,COALESCE(:tr,0)) "
            "ON DUPLICATE KEY UPDATE directive=:dir, directive_reason=:re, directive_until=:un, trusted=COALESCE(:tr, trusted)",
            t=tenant_id, u=user_id, d=device_id, dir=directive, re=reason[:255], un=until.replace(tzinfo=None) if until else None, tr=trusted)

    def is_trusted(self, tenant_id, user_id, device_id):
        return bool(self._exec("SELECT trusted FROM client_guard_device WHERE tenant_id=:t AND user_id=:u AND device_id=:d",
                               t=tenant_id, u=user_id, d=device_id).scalar())


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _local_date(dt: datetime):
    return (_utc(dt) + timedelta(hours=8)).date()
