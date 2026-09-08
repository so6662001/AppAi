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


class RdpHardening(BaseModel):
    """自研 RDP 启动器对 MsRdpClient 控件的加固设置(与 C# RdpHardening 字段一致)."""
    redirect_clipboard: bool = False
    redirect_clipboard_when_low_risk: bool = True
    redirect_drives: bool = False
    redirect_printers: bool = True
    redirect_smart_cards: bool = True
    redirect_ports: bool = False
    redirect_devices: bool = False
    redirect_pnp_drives: bool = False
    start_program_only: bool = True
    launcher_exclude_from_capture: bool = True
    disconnect_at_level: str = "Critical"
    # 服务端专用:未配对(绕过自研启动器、用 mstsc / 第三方客户端直连)的远程会话导出如何处理:allow / approval / deny
    unpaired_remote_export: str = "approval"
    # 服务端专用:启动器本地风险达到该分数时,建议关闭剪贴板 / 拒绝连接
    clipboard_off_score: float = 30
    deny_connect_score: float = 60
    # 服务端专用:启动票据有效期(秒)
    ticket_ttl_sec: int = 300


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
    exclude_from_capture_in_remote_session: bool = False   # RDP 中开启会让合法用户也看到黑块
    remote_session_force_visible_watermark: bool = True
    accessibility_mode: bool = False
    rdp: RdpHardening = Field(default_factory=RdpHardening)


class GuardEvent(BaseModel):
    event_id: str
    tenant_id: int
    user_id: int
    device_id: str = ""
    session_id: str = ""
    side: str = "local"              # local / remote / launcher
    link_id: Optional[str] = None
    client_name: Optional[str] = None
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


# ----------------------------------------------------------------- 双端绑定(自研 RDP 启动器 ↔ 远程会话内 ERP)
class SessionLaunchIn(BaseModel):
    tenant_id: int
    user_id: int
    device_id: str
    machine_name: str = ""
    local_score: float = 0
    local_level: str = "Low"


class SessionLaunchOut(BaseModel):
    ticket: str = ""
    link_id: str = ""
    expires_at: int = 0
    connect_advice: str = "allow"    # allow / clipboard_off / deny
    message: Optional[str] = None


class SessionBindIn(BaseModel):
    tenant_id: int
    user_id: int
    ticket: Optional[str] = None
    client_name: str = ""
    client_address: str = ""
    remote_device_id: str = ""


class SessionBindOut(BaseModel):
    linked: bool
    link_id: Optional[str] = None
    device_id: Optional[str] = None
    matched_by: str = "none"         # ticket / client_name / none
    message: Optional[str] = None


class SessionLinkRecord(BaseModel):
    link_id: str
    tenant_id: int
    user_id: int
    launcher_device_id: str
    machine_name: str = ""
    ticket_nonce: str = ""
    ticket_expires_at: int = 0
    local_score: float = 0
    status: str = "issued"           # issued / bound / expired
    remote_device_id: Optional[str] = None
    client_name: Optional[str] = None
    client_address: Optional[str] = None
    created_at: datetime
    bound_at: Optional[datetime] = None


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
