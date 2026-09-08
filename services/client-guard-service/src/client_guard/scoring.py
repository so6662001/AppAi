"""服务端独立评分.

客户端上报的 score 只是参考(可被篡改);服务端只信任 *事实类* 事件
(signal 的 kind/时间戳、export 的行数),用同样的 权重 × 半衰期 × cap 模型重新算分,
并叠加只有服务端能看到的信号:
  - 跨设备并发(同一账号 2 台以上设备 5 分钟内都在活动)
  - 导出频率 / 行数超配额
  - 非工作时间大量操作
"""
from __future__ import annotations
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .models import GuardEvent, GuardPolicy, SignalWeight

DEFAULT_WEIGHTS: dict[str, SignalWeight] = {
    "KnownAutomationProcess": SignalWeight(weight=40, half_life_sec=1800, cap=60),
    "RemoteControlProcess": SignalWeight(weight=10, half_life_sec=1800, cap=15),
    "InjectedInput": SignalWeight(weight=3, half_life_sec=120, cap=40),
    "UiaProbing": SignalWeight(weight=25, half_life_sec=600, cap=50),
    "UiaCoreLoaded": SignalWeight(weight=20, half_life_sec=3600, cap=20),
    "RoboticTiming": SignalWeight(weight=20, half_life_sec=300, cap=40),
    "TeleportClick": SignalWeight(weight=4, half_life_sec=180, cap=30),
    "RepeatedExactClick": SignalWeight(weight=10, half_life_sec=300, cap=20),
    "SuperhumanRate": SignalWeight(weight=15, half_life_sec=300, cap=30),
    "RhythmicPaging": SignalWeight(weight=20, half_life_sec=600, cap=40),
    "ClipboardBurst": SignalWeight(weight=15, half_life_sec=300, cap=30),
    "ExportAnomaly": SignalWeight(weight=20, half_life_sec=1800, cap=40),
    "RemoteSession": SignalWeight(weight=10, half_life_sec=7200, cap=10),
    "UnpairedRemoteSession": SignalWeight(weight=25, half_life_sec=7200, cap=25),
    "DebuggerAttached": SignalWeight(weight=30, half_life_sec=3600, cap=30),
    "VirtualMachine": SignalWeight(weight=5, half_life_sec=7200, cap=5),
    "ServerDirective": SignalWeight(weight=100, half_life_sec=600, cap=100),
    # 仅服务端
    "MultiDeviceConcurrent": SignalWeight(weight=25, half_life_sec=900, cap=25),
    "ServerExportQuota": SignalWeight(weight=30, half_life_sec=3600, cap=60),
    "OffHoursBulk": SignalWeight(weight=15, half_life_sec=3600, cap=15),
}


def weight_of(policy: GuardPolicy, kind: str) -> SignalWeight:
    return policy.weights.get(kind) or DEFAULT_WEIGHTS.get(kind) or SignalWeight(weight=0)


def level_of(policy: GuardPolicy, score: float) -> str:
    t = policy.thresholds
    if score >= t.get("critical", 85):
        return "Critical"
    if score >= t.get("high", 60):
        return "High"
    if score >= t.get("elevated", 30):
        return "Elevated"
    return "Low"


def _decay(weight: float, at: datetime, now: datetime, half_life: float) -> float:
    if half_life <= 0:
        return weight
    elapsed = (now - at).total_seconds()
    if elapsed <= 0:
        return weight
    return weight * math.pow(0.5, elapsed / half_life)


def score_signals(policy: GuardPolicy, signals: Iterable[tuple[str, datetime, float | None]], now: datetime) -> tuple[float, dict[str, float]]:
    """signals: (kind, at, weight_override). 返回 (总分, 分解)."""
    per_kind: dict[str, float] = defaultdict(float)
    for kind, at, w in signals:
        sw = weight_of(policy, kind)
        base = w if (w is not None and kind in ("ServerDirective",)) else sw.weight   # 客户端权重不可信,除服务端指令
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        per_kind[kind] += _decay(base, at, now, sw.half_life_sec)
    breakdown = {k: min(v, weight_of(policy, k).cap) for k, v in per_kind.items()}
    return min(100.0, sum(breakdown.values())), breakdown


def server_only_signals(policy: GuardPolicy, events: list[GuardEvent], now: datetime,
                        exports_last_hour: int, rows_today: int) -> list[tuple[str, datetime, float | None]]:
    """从事件流派生只有服务端能算的信号."""
    out: list[tuple[str, datetime, float | None]] = []
    recent = [e for e in events if (now - _utc(e.at)) <= timedelta(minutes=5)]
    if len(concurrent_devices(recent)) >= 2:
        out.append(("MultiDeviceConcurrent", now, None))
    q = policy.export_quota
    if exports_last_hour > q.max_exports_per_hour or rows_today > q.max_rows_per_day:
        out.append(("ServerExportQuota", now, None))
    off_hours_exports = [e for e in events if e.type == "export" and not (7 <= _local_hour(e.at) <= 21)
                         and (now - _utc(e.at)) <= timedelta(hours=6)]
    if len(off_hours_exports) >= 3:
        out.append(("OffHoursBulk", now, None))
    return out


def concurrent_devices(recent: list[GuardEvent]) -> set[str]:
    """把"物理设备"数出来:
    - 自研启动器(side=launcher)与它绑定的远程会话(side=remote,同 link_id 或绑定后沿用同一 device_id)算 1 台;
    - 没配对的远程会话按 client_name(RDP 客户机名)归并,没有 client_name 才退化为 device_id。
    这样"一台 PC 通过启动器登录 RDS"不会被误报为多设备。
    """
    launchers = [e for e in recent if e.side == "launcher" and e.device_id]
    launcher_devices = {e.device_id for e in launchers}
    launcher_links = {e.link_id for e in launchers if e.link_id}
    launcher_names = {e.client_name.lower() for e in launchers if e.client_name}
    devices: set[str] = set(launcher_devices)
    for e in recent:
        if e.side == "launcher" or not e.device_id:
            continue
        if e.side == "remote":
            if e.device_id in launcher_devices:            # 绑定后沿用启动器指纹
                continue
            if e.link_id and e.link_id in launcher_links:  # 绑定前发出的少量事件,同一 link
                continue
            name = (e.client_name or "").lower()
            if name and name in launcher_names:            # 无票据:RDP 客户机名 = 启动器机器名
                continue
            devices.add("client:" + name if name else e.device_id)
        else:
            devices.add(e.device_id)
    return devices


def _utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _local_hour(dt: datetime) -> int:
    # 部署默认 Asia/Shanghai;事件时间统一按 UTC+8 判断工作时间
    return (_utc(dt) + timedelta(hours=8)).hour
