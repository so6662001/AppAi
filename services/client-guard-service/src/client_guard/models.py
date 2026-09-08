"""Pydantic 模型 - 与 C# SDK 的 JSON 字段一致."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class ExportQuota(BaseModel):
    max_rows_per_export: int = 20000
    max_exports_per_hour: int = 10
    max_rows_per_day: int = 200000
    approval_threshold_rows: int = 5000
    delay_min_ms: int = 0
    delay_max_ms: int = 0
    allowed_hours: list[int] = Field(default_factory=list)


class SignalWeight(BaseModel):
    weight: float
    half_life_sec: float = 600
    cap: float = 100


class GuardPolicy(BaseModel):
    version: int = 1
    thresholds: dict[str, float] = Field(default_factory=lambda: {"elevated": 30, "high": 60, "critical": 85})
    weights: dict[str, SignalWeight] = Field(default_factory=dict)
    automation_processes: list[str] = Field(default_factory=list)
    remote_control_processes: list[str] = Field(default_factory=list)
    accessibility_whitelist: list[str] = Field(default_factory=lambda: ["nvda", "jfw", "narrator", "zdsr", "zhengdu"])
    sensitive_columns: list[str] = Field(default_factory=lambda: [
        "customer_name", "customer_phone", "contact_phone", "unit_price", "gross_profit",
        "supplier_name", "cost_price", "commission", "credit_limit", "bank_account"])
    export_quota: ExportQuota = Field(default_factory=ExportQuota)
    uia_probe_per_minute: int = 40
    clipboard_burst_count: int = 10
    remote_session_injected_multiplier: float = 0.2
    exclude_from_capture: bool = True
    accessibility_mode: bool = False


class GuardEvent(BaseModel):
    event_id: str
    tenant_id: int
    user_id: int
    device_id: str = ""
    session_id: str = ""
    at: datetime
    type: str = "signal"
    kind: Optional[str] = None
    weight: Optional[float] = None
    score: float = 0
    level: str = "Low"
    detail: Optional[str] = None
    breakdown: Optional[dict[str, float]] = None
    client_version: str = ""
    os: str = ""


class TelemetryResponse(BaseModel):
    accepted: int
    directive: str = "none"          # none / degrade / lock
    message: Optional[str] = None
    policy_version: Optional[int] = None
    server_score: float = 0


class ExportRequestIn(BaseModel):
    tenant_id: int
    user_id: int
    data_set: str
    row_count: int
    device_id: str = ""
    risk_score: float = 0
    reason: str = ""


class ExportRequestOut(BaseModel):
    status: str                      # approved / pending / denied
    request_id: str
    token: Optional[str] = None
    message: Optional[str] = None
    approver: Optional[str] = None


class ApproveIn(BaseModel):
    approver_id: int
    approver_name: str
    approve: bool = True
    note: str = ""
    max_rows: Optional[int] = None
    ttl_minutes: int = 30


class DeviceDirectiveIn(BaseModel):
    directive: str                   # none / degrade / lock
    reason: str = ""
    minutes: int = 60
    trusted: Optional[bool] = None


class ExportRequestRecord(BaseModel):
    request_id: str
    tenant_id: int
    user_id: int
    device_id: str = ""
    data_set: str
    row_count: int
    risk_score: float = 0
    reason: str = ""
    status: str = "pending"
    approver_id: Optional[int] = None
    approver_name: Optional[str] = None
    approve_note: Optional[str] = None
    token: Optional[str] = None
    token_expires_at: Optional[int] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    extra: dict[str, Any] = Field(default_factory=dict)
