using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows;
using SteelGuard.AntiRpa.Windows.Protection;

namespace SteelGuard.AntiRpa.RdpLauncher
{
    /// <summary>启动器接入参数。</summary>
    public sealed class RdpLauncherOptions
    {
        public long TenantId { get; set; }
        public long UserId { get; set; }
        public string UserName { get; set; } = "";
        /// <summary>client-guard-service 地址;为空则离线(只做本地加固 + 本地日志,不申请票据)。</summary>
        public string? PolicyEndpoint { get; set; }
        public string? ApiToken { get; set; }
        /// <summary>服务器上 ERP 客户端的完整路径(用于 StartProgram,只发布程序不给桌面)。为空则不设置 StartProgram。</summary>
        public string? ErpStartProgram { get; set; }
        public string? ErpWorkDir { get; set; }
        /// <summary>ERP 之外附加的命令行参数。</summary>
        public string? ErpExtraArgs { get; set; }
        /// <summary>服务不可达时是否拒绝连接(默认 false:降级为"加固 + 无票据",远程端按客户机名兜底匹配)。</summary>
        public bool FailClosed { get; set; } = false;
        public string ClientVersion { get; set; } = "launcher-1.0.0";
        public GuardPolicy? InitialPolicy { get; set; }
        public string? LocalLogFile { get; set; }
    }

    /// <summary>PrepareConnect 结果。</summary>
    public sealed class PrepareConnectResult
    {
        public bool CanConnect { get; set; }
        public string? DenyReason { get; set; }
        public string? Ticket { get; set; }
        public string? LinkId { get; set; }
        public bool ClipboardAllowed { get; set; }
        public HardeningReport? Hardening { get; set; }
        public string ConnectAdvice { get; set; } = "allow";
    }

    /// <summary>
    /// 自研 RDP 启动器侧的门面(本地 PC 上运行,进程内承载 MsRdpClient ActiveX)。
    /// <para>
    /// 本地这一端是防护最有效的位置:低级钩子看到的是真实硬件输入(WorkBuddy / RPA 的 SendInput 带 INJECTED 标志),
    /// 进程扫描看到的是本地进程,启动器窗口是本地普通窗口(可加 WDA_EXCLUDEFROMCAPTURE,
    /// 截屏 / 录屏 / AI 桌面代理的 observe_ui 全部得到黑块),RDP 控件的剪贴板 / 驱动器重定向由我们决定。
    /// </para>
    /// 用法(VB.NET):
    /// <code>
    /// guard = RdpLauncherGuard.Start(Me, opts)
    /// Dim r = Await guard.PrepareConnectAsync(AxRdp)   ' 加固 + 申请票据 + 设置 StartProgram
    /// If r.CanConnect Then AxRdp.Connect()
    /// </code>
    /// </summary>
    public sealed class RdpLauncherGuard : IDisposable
    {
        public static RdpLauncherGuard? Current { get; private set; }

        public SteelGuardHost Host { get; }
        public RdpLauncherOptions Options { get; }
        public GuardPolicy Policy => Host.Policy;
        public string? Ticket { get; private set; }

        private readonly Form _form;
        private readonly List<object> _controls = new List<object>();
        private bool _disposed;

        /// <summary>启动器主动断开 RDP(参数为原因);宿主可弹提示。</summary>
        public event EventHandler<string>? DisconnectRequested;

        private RdpLauncherGuard(Form form, RdpLauncherOptions o)
        {
            _form = form;
            Options = o;
            Host = SteelGuardHost.Start(new GuardOptions
            {
                TenantId = o.TenantId, UserId = o.UserId, UserName = o.UserName,
                PolicyEndpoint = o.PolicyEndpoint, ApiToken = o.ApiToken,
                ClientVersion = o.ClientVersion, InitialPolicy = o.InitialPolicy,
                LocalLogFile = o.LocalLogFile ?? System.IO.Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SteelGuard", "launcher-events.jsonl"),
                Side = "launcher",
                BindRemoteSession = false,
                EnableInputHooks = true,
            });
            Host.LevelChanged += OnLevelChanged;
            Host.SessionLockRequested += (_, msg) => DisconnectAll("lock: " + msg);
        }

        /// <summary>在启动器窗体 Load 时调用(UI 线程)。</summary>
        public static RdpLauncherGuard Start(Form launcherForm, RdpLauncherOptions options)
        {
            if (launcherForm == null) throw new ArgumentNullException(nameof(launcherForm));
            Current?.Dispose();
            var g = new RdpLauncherGuard(launcherForm, options ?? throw new ArgumentNullException(nameof(options)));
            Current = g;
            g.ProtectLauncherWindow();
            return g;
        }

        /// <summary>
        /// 启动器窗口防截屏 + UIA 探针。本地 PC 上不是远程会话,WDA_EXCLUDEFROMCAPTURE 直接有效:
        /// 截屏工具 / 录屏 / WorkBuddy 的屏幕读取拿到的是黑块,而用户肉眼正常。
        /// (若启动器本身又跑在别的远程会话里,SteelGuardHost 会按策略自动跳过。)
        /// </summary>
        private void ProtectLauncherWindow()
        {
            if (Policy.Rdp.LauncherExcludeFromCapture)
                Host.Protect(_form);
            else
                Host.UiaProbe.Attach(_form);
        }

        /// <summary>
        /// Connect 之前调用:申请启动票据(携带本地风险)→ 加固 RDP 控件 → 设置 StartProgram(携带票据)。
        /// 传入 AxHost 控件或其 GetOcx()。
        /// </summary>
        public async Task<PrepareConnectResult> PrepareConnectAsync(object rdpControl, CancellationToken ct = default)
        {
            if (rdpControl == null) throw new ArgumentNullException(nameof(rdpControl));
            Attach(rdpControl);
            var res = new PrepareConnectResult();

            var level = Host.Engine.Level;
            if (level >= Policy.Rdp.DisconnectAtLevel)
            {
                res.CanConnect = false;
                res.DenyReason = $"本机风险等级 {level},拒绝建立远程连接(检测到自动化 / 远控工具或异常输入)";
                return res;
            }

            string? advice = "allow";
            if (Host.Api != null)
            {
                var t = await Host.Api.RequestLaunchTicketAsync(Options.TenantId, Options.UserId, Host.DeviceId, Environment.MachineName,
                    Host.Engine.Score, level.ToString(), ct).ConfigureAwait(false);
                if (t == null)
                {
                    if (Options.FailClosed)
                    {
                        res.CanConnect = false;
                        res.DenyReason = "防护服务不可达,已按策略拒绝连接";
                        return res;
                    }
                    advice = "allow";
                }
                else
                {
                    advice = t.ConnectAdvice;
                    if (advice == "deny")
                    {
                        res.CanConnect = false;
                        res.DenyReason = t.Message ?? "服务端拒绝本次连接";
                        res.ConnectAdvice = advice;
                        return res;
                    }
                    if (!string.IsNullOrEmpty(t.Ticket))
                    {
                        Ticket = t.Ticket;
                        res.Ticket = t.Ticket;
                        res.LinkId = t.LinkId;
                        Host.AttachLink(t.LinkId);
                    }
                }
            }

            var allowClip = level == RiskLevel.Low && advice != "clipboard_off";
            string? startProgram = null;
            if (!string.IsNullOrWhiteSpace(Options.ErpStartProgram))
            {
                startProgram = Ticket != null
                    ? GuardTicket.BuildCommandLine(Options.ErpStartProgram!, Ticket, Options.ErpExtraArgs)
                    : (Options.ErpStartProgram + (string.IsNullOrWhiteSpace(Options.ErpExtraArgs) ? "" : " " + Options.ErpExtraArgs));
            }

            res.Hardening = RdpControlHardening.Apply(rdpControl, Policy.Rdp, allowClip, startProgram, Options.ErpWorkDir);
            res.ClipboardAllowed = res.Hardening.ClipboardRedirected;
            res.ConnectAdvice = advice ?? "allow";
            res.CanConnect = true;
            return res;
        }

        /// <summary>登记一个 RDP 控件(风险达阈值时统一断开)。PrepareConnectAsync 会自动登记。</summary>
        public void Attach(object rdpControl)
        {
            if (!_controls.Contains(rdpControl)) _controls.Add(rdpControl);
        }

        /// <summary>连接成功后(OnLoginComplete)调用:复核加固仍然有效,并记录一次心跳。</summary>
        public bool VerifyAfterConnect(object rdpControl)
        {
            var ok = RdpControlHardening.VerifyLockedDown(rdpControl, Policy.Rdp, Host.Engine.Level == RiskLevel.Low);
            if (!ok) Host.Engine.Report(SignalKind.ExportAnomaly, "rdp redirection tampered after hardening");
            return ok;
        }

        /// <summary>手动断开全部会话。</summary>
        public void DisconnectAll(string reason)
        {
            foreach (var c in _controls.ToList())
                RdpControlHardening.Disconnect(c);
            var h = DisconnectRequested;
            if (h == null) return;
            if (_form.IsHandleCreated && _form.InvokeRequired) _form.BeginInvoke(new Action(() => h(this, reason)));
            else h(this, reason);
        }

        private void OnLevelChanged(object? sender, RiskLevelChangedEventArgs e)
        {
            if (e.Current >= Policy.Rdp.DisconnectAtLevel)
                DisconnectAll($"风险等级 {e.Current}({e.Trigger.Kind}),已断开远程连接");
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            Host.LevelChanged -= OnLevelChanged;
            Host.Dispose();
            if (Current == this) Current = null;
        }
    }
}
