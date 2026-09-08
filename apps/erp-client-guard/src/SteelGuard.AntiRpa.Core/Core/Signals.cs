using System;

namespace SteelGuard.AntiRpa.Core
{
    /// <summary>检测信号类型。每个类型有默认权重与半衰期,可被服务端策略覆盖。</summary>
    public enum SignalKind
    {
        /// <summary>发现已知 RPA / 自动化 Agent 进程。</summary>
        KnownAutomationProcess,
        /// <summary>发现远程控制软件(TeamViewer / ToDesk / 向日葵 ...)。</summary>
        RemoteControlProcess,
        /// <summary>低级钩子捕获到带 INJECTED 标志的键鼠输入。</summary>
        InjectedInput,
        /// <summary>WM_GETOBJECT 频率超阈值(UIA / MSAA 客户端在读控件树)。</summary>
        UiaProbing,
        /// <summary>UIAutomationCore.dll 在运行期被外部加载进本进程。</summary>
        UiaCoreLoaded,
        /// <summary>事件节律过于规整(变异系数极低)。</summary>
        RoboticTiming,
        /// <summary>鼠标无轨迹瞬移后点击。</summary>
        TeleportClick,
        /// <summary>同一像素反复点击。</summary>
        RepeatedExactClick,
        /// <summary>超越人类的操作速率。</summary>
        SuperhumanRate,
        /// <summary>固定节拍翻页(爬全表签名)。</summary>
        RhythmicPaging,
        /// <summary>短时间内高频复制到剪贴板。</summary>
        ClipboardBurst,
        /// <summary>导出频率 / 行数异常。</summary>
        ExportAnomaly,
        /// <summary>RDP / 远程会话。</summary>
        RemoteSession,
        /// <summary>调试器附加。</summary>
        DebuggerAttached,
        /// <summary>运行在虚拟机中。</summary>
        VirtualMachine,
        /// <summary>服务端下发的指令(强制降级 / 锁定)。</summary>
        ServerDirective,
    }

    public enum RiskLevel { Low = 0, Elevated = 1, High = 2, Critical = 3 }

    /// <summary>受保护操作类型。</summary>
    public enum GuardOperation { View, Copy, Export, Print }

    /// <summary>数据敏感级别(用于脱敏与网格护盾强度)。</summary>
    public enum DataSensitivity { Public = 0, Internal = 1, Confidential = 2, High = 3 }

    /// <summary>一次检测产生的信号。</summary>
    public sealed class Signal
    {
        public SignalKind Kind { get; }
        public double Weight { get; }
        public DateTimeOffset At { get; }
        public string? Detail { get; }

        public Signal(SignalKind kind, double weight, DateTimeOffset at, string? detail = null)
        {
            Kind = kind;
            Weight = weight;
            At = at;
            Detail = detail;
        }

        public override string ToString() => $"{Kind}({Weight:0.#}) {Detail}";
    }

    /// <summary>可注入的时钟,便于测试。</summary>
    public interface IGuardClock
    {
        DateTimeOffset Now { get; }
    }

    public sealed class SystemClock : IGuardClock
    {
        public static readonly SystemClock Instance = new SystemClock();
        public DateTimeOffset Now => DateTimeOffset.UtcNow;
    }

    /// <summary>可手动推进的时钟(测试用)。</summary>
    public sealed class ManualClock : IGuardClock
    {
        public DateTimeOffset Now { get; set; }
        public ManualClock(DateTimeOffset start) { Now = start; }
        public void Advance(TimeSpan by) => Now = Now.Add(by);
    }
}
