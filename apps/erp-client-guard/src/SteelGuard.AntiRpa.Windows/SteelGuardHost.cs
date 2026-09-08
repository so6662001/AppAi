using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Core.Telemetry;
using SteelGuard.AntiRpa.Windows.Detection;
using SteelGuard.AntiRpa.Windows.Protection;

namespace SteelGuard.AntiRpa.Windows
{
    /// <summary>接入参数。</summary>
    public sealed class GuardOptions
    {
        public long TenantId { get; set; }
        public long UserId { get; set; }
        public string UserName { get; set; } = "";
        /// <summary>设备指纹;为空则按 机器名 + 用户名 + MAC 派生。</summary>
        public string? DeviceId { get; set; }
        /// <summary>client-guard-service 地址,例如 https://api.example.com/v1/client-guard;为空则离线模式(默认策略 + 本地日志)。</summary>
        public string? PolicyEndpoint { get; set; }
        public string? ApiToken { get; set; }
        /// <summary>离线模式下的本地 HMAC 审批密钥(可选)。</summary>
        public string? OfflineApprovalSecret { get; set; }
        /// <summary>蜜罐生成密钥(与服务端一致,用于泄露溯源)。</summary>
        public string CanarySecret { get; set; } = "change-me";
        public string ClientVersion { get; set; } = "1.0.0";
        /// <summary>本地遥测落盘文件(服务不可达时)。</summary>
        public string? LocalLogFile { get; set; } = System.IO.Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SteelGuard", "events.jsonl");
        public TimeSpan ProbeInterval { get; set; } = TimeSpan.FromSeconds(30);
        public TimeSpan PolicyRefreshInterval { get; set; } = TimeSpan.FromMinutes(10);
        /// <summary>是否安装低级键鼠钩子(默认 true)。</summary>
        public bool EnableInputHooks { get; set; } = true;
        /// <summary>初始策略(为空用内置默认,之后被服务端下发覆盖)。</summary>
        public GuardPolicy? InitialPolicy { get; set; }
    }

    /// <summary>
    /// SDK 门面:一行 <c>SteelGuardHost.Start(options)</c> 完成所有检测器装配;
    /// 业务代码只需 <see cref="Protect(Form)"/>、<see cref="Decide"/>、<see cref="RequestExportAsync"/>。
    /// 必须在 UI 线程调用 Start(低级钩子需要消息循环)。
    /// </summary>
    public sealed class SteelGuardHost : IDisposable
    {
        public static SteelGuardHost? Current { get; private set; }

        public GuardOptions Options { get; }
        public RiskEngine Engine { get; }
        public BehaviorAnalyzer Analyzer { get; }
        public ExportGovernor Exports { get; }
        public IGuardClock Clock { get; }
        public UiAutomationProbe UiaProbe { get; }
        public EnvironmentProbe EnvProbe { get; }
        public string DeviceId { get; }
        public string SessionId { get; } = Guid.NewGuid().ToString("N");
        public GuardPolicy Policy => Engine.Policy;

        private readonly InputInjectionMonitor? _input;
        private readonly ClipboardGuard _clipboard;
        private readonly ITelemetrySink _sink;
        private readonly GuardApiClient? _api;
        private readonly IApprovalVerifier? _verifier;
        private readonly System.Windows.Forms.Timer _probeTimer;
        private readonly System.Windows.Forms.Timer _policyTimer;
        private readonly List<Form> _protected = new List<Form>();
        private bool _disposed;

        /// <summary>风险等级变化(UI 线程外触发,需 Invoke)。</summary>
        public event EventHandler<RiskLevelChangedEventArgs>? LevelChanged;
        /// <summary>
        /// 人机挑战处理器:宿主弹出拖动验证 / 二次登录对话框,返回是否通过。
        /// 未设置时,High 等级的导出直接拒绝。
        /// </summary>
        public Func<GuardDecision, Task<bool>>? ChallengeHandler { get; set; }
        /// <summary>要求锁定会话。</summary>
        public event EventHandler<string>? SessionLockRequested;

        private SteelGuardHost(GuardOptions options)
        {
            Options = options ?? throw new ArgumentNullException(nameof(options));
            Clock = SystemClock.Instance;
            DeviceId = options.DeviceId ?? ComputeDeviceId();
            Engine = new RiskEngine(options.InitialPolicy ?? GuardPolicy.Default, Clock);
            Analyzer = new BehaviorAnalyzer(Engine);
            Exports = new ExportGovernor(Engine, Clock);
            UiaProbe = new UiAutomationProbe(Engine, Clock);
            EnvProbe = new EnvironmentProbe(Engine);
            _clipboard = new ClipboardGuard(Analyzer, Clock);

            if (!string.IsNullOrEmpty(options.PolicyEndpoint))
            {
                _api = new GuardApiClient(options.PolicyEndpoint!, options.ApiToken);
                _verifier = new RemoteApprovalVerifier(_api);
                var http = new HttpTelemetrySink(options.PolicyEndpoint!, options.ApiToken, TimeSpan.FromSeconds(15), options.LocalLogFile);
                http.DirectiveReceived += OnDirective;
                _sink = http;
            }
            else
            {
                _sink = new FileTelemetrySink(options.LocalLogFile ?? "steelguard-events.jsonl");
                if (!string.IsNullOrEmpty(options.OfflineApprovalSecret))
                    _verifier = new ApprovalTokenVerifier(options.OfflineApprovalSecret!, options.TenantId, options.UserId);
            }

            if (options.EnableInputHooks) _input = new InputInjectionMonitor(Analyzer, Clock);

            Engine.SignalReceived += (_, s) => Emit(new GuardEvent
            {
                Type = "signal", Kind = s.Kind.ToString(), Weight = s.Weight, Detail = s.Detail,
            });
            Engine.LevelChanged += OnLevelChanged;

            _probeTimer = new System.Windows.Forms.Timer { Interval = (int)options.ProbeInterval.TotalMilliseconds };
            _probeTimer.Tick += (_, __) => Poll();
            _policyTimer = new System.Windows.Forms.Timer { Interval = (int)options.PolicyRefreshInterval.TotalMilliseconds };
            _policyTimer.Tick += async (_, __) => await RefreshPolicyAsync().ConfigureAwait(false);
        }

        /// <summary>启动(UI 线程)。</summary>
        public static SteelGuardHost Start(GuardOptions options)
        {
            Current?.Dispose();
            var h = new SteelGuardHost(options);
            Current = h;
            try { h._input?.Start(); } catch (Exception ex) { h.Emit(new GuardEvent { Type = "error", Detail = "hook: " + ex.Message }); }
            try { h._clipboard.Start(); } catch { /* ignore */ }
            h.Poll();
            h._probeTimer.Start();
            h._policyTimer.Start();
            _ = h.RefreshPolicyAsync();
            h.Emit(new GuardEvent { Type = "heartbeat", Detail = "start" });
            return h;
        }

        // ------------------------------------------------------------------
        /// <summary>保护一个窗体:防截屏 + WM_GETOBJECT 探针 + 按等级隐藏 UIA 树。</summary>
        public void Protect(Form form)
        {
            if (form == null) throw new ArgumentNullException(nameof(form));
            if (_protected.Contains(form)) return;
            _protected.Add(form);
            if (Policy.ExcludeFromCapture) ScreenCaptureGuard.Apply(form, true);
            UiaProbe.Attach(form);
            form.FormClosed += (_, __) => _protected.Remove(form);
            ApplyLevel(Engine.Level);
        }

        /// <summary>对一次操作做即时决策(不含配额;导出请用 <see cref="RequestExportAsync"/>)。</summary>
        public GuardDecision Decide(GuardOperation op, DataSensitivity sensitivity = DataSensitivity.Internal, int rowCount = 0) =>
            PolicyEngine.Decide(Policy, Engine.Level, Engine.Score, op, sensitivity, rowCount);

        /// <summary>
        /// 申请导出:策略 + 本地配额 + (必要时)服务端审批。
        /// 返回 Allowed=true 时调用方再执行真正导出,并在完成后调用 <see cref="RecordExport"/>。
        /// </summary>
        public async Task<GuardDecision> RequestExportAsync(string dataSet, int rowCount,
            DataSensitivity sensitivity = DataSensitivity.Confidential, string? approvalToken = null,
            TimeSpan? waitForApproval = null, CancellationToken ct = default)
        {
            var req = new ExportRequest { DataSet = dataSet, RowCount = rowCount, Sensitivity = sensitivity, ApprovalToken = approvalToken };
            var d = Exports.Evaluate(req, _verifier);

            if (d.RequiresChallenge && !d.Has(GuardAction.Deny))
            {
                var passed = ChallengeHandler != null && await ChallengeHandler(d).ConfigureAwait(false);
                if (!passed)
                {
                    d.Actions = (d.Actions & ~GuardAction.Allow) | GuardAction.Deny;
                    d.Reason = ChallengeHandler == null ? "风险较高且未配置人工验证,已拒绝" : "未通过人工验证";
                    Emit("export_decision", d, dataSet);
                    return d;
                }
                ChallengePassed();
                d = Exports.Evaluate(req, _verifier);   // 通过后风险清零,重新评估
            }

            if (d.RequiresApproval && string.IsNullOrEmpty(approvalToken) && !d.Has(GuardAction.Deny) && _api != null)
            {
                var r = await _api.RequestExportAsync(Options.TenantId, Options.UserId, dataSet, rowCount, DeviceId, Engine.Score, d.Reason, ct).ConfigureAwait(false);
                if (r == null || r.Status == "denied")
                {
                    d.Actions = (d.Actions & ~GuardAction.Allow) | GuardAction.Deny;
                    d.Reason = "服务端拒绝导出:" + (r?.Message ?? "unknown");
                }
                else if (r.Status == "approved" && !string.IsNullOrEmpty(r.Token))
                {
                    req.ApprovalToken = r.Token;
                    d = Exports.Evaluate(req, _verifier);
                }
                else if (r.Status == "pending")
                {
                    var deadline = Clock.Now + (waitForApproval ?? TimeSpan.Zero);
                    ExportRequestResult? p = r;
                    while (Clock.Now < deadline && p != null && p.Status == "pending" && !ct.IsCancellationRequested)
                    {
                        await Task.Delay(TimeSpan.FromSeconds(5), ct).ConfigureAwait(false);
                        p = await _api.PollExportAsync(r.RequestId, ct).ConfigureAwait(false);
                    }
                    if (p != null && p.Status == "approved" && !string.IsNullOrEmpty(p.Token))
                    {
                        req.ApprovalToken = p.Token;
                        d = Exports.Evaluate(req, _verifier);
                    }
                    else
                    {
                        d.Actions = (d.Actions & ~GuardAction.Allow) | GuardAction.RequireApproval;
                        d.Reason = $"已提交审批,单号 {r.RequestId},审批通过后可导出";
                        d.Explanations.Add("pending:" + r.RequestId);
                    }
                }
            }

            if (d.Allowed && d.Has(GuardAction.Delay) && d.DelayMs > 0)
                await Task.Delay(d.DelayMs, ct).ConfigureAwait(false);

            Emit("export_decision", d, dataSet);
            return d;
        }

        /// <summary>导出完成后记录(配额统计 + 遥测)。</summary>
        public void RecordExport(string dataSet, int rows, WatermarkContext wm)
        {
            Exports.RecordExport(rows);
            Emit(new GuardEvent { Type = "export", Detail = $"{dataSet} rows={rows} export_id={wm.ExportId}" });
        }

        public WatermarkContext NewWatermark() => new WatermarkContext
        {
            TenantId = Options.TenantId, UserId = Options.UserId, UserName = Options.UserName, DeviceId = DeviceId, At = DateTimeOffset.Now,
        };

        public CanaryData.Context NewCanaryContext(int count = 2) => new CanaryData.Context
        {
            TenantId = Options.TenantId, UserId = Options.UserId, Day = DateTimeOffset.Now, Secret = Options.CanarySecret, Count = count,
        };

        /// <summary>
        /// 一站式处理导出数据:截断 → 脱敏 → 隐形水印 → 蜜罐。返回可直接写 Excel 的行。
        /// </summary>
        public List<Dictionary<string, object?>> PrepareExportRows(IEnumerable<Dictionary<string, object?>> rows, GuardDecision d, WatermarkContext wm)
        {
            var list = rows.ToList();
            if (d.RowLimit > 0 && list.Count > d.RowLimit) list = list.Take(d.RowLimit).ToList();
            if (d.Has(GuardAction.Mask)) list = DataMasker.MaskRows(list, Policy.SensitiveColumns);
            if (d.Has(GuardAction.Watermark)) list = Watermark.Apply(list, wm, Policy.SensitiveColumns);
            if (d.Has(GuardAction.Canary)) list = CanaryData.Inject(list, NewCanaryContext());
            return list;
        }

        /// <summary>人机挑战通过后调用:清零累计信号(进程类信号会在下一轮探测中重新出现)。</summary>
        public void ChallengePassed()
        {
            Engine.Reset();
            EnvProbe.ResetReported();
            Poll();
            Emit(new GuardEvent { Type = "challenge", Detail = "passed" });
        }

        // ------------------------------------------------------------------
        private void Poll()
        {
            try
            {
                EnvProbe.Poll();
                UiaProbe.Poll();
                Engine.Reevaluate();
            }
            catch (Exception ex) { Emit(new GuardEvent { Type = "error", Detail = "poll: " + ex.Message }); }
        }

        public async Task RefreshPolicyAsync()
        {
            if (_api == null) return;
            var p = await _api.FetchPolicyAsync(Options.TenantId).ConfigureAwait(false);
            if (p == null) return;
            Engine.UpdatePolicy(p);
            EnvProbe.UpdatePolicy(p);
        }

        private void OnLevelChanged(object? sender, RiskLevelChangedEventArgs e)
        {
            Emit(new GuardEvent { Type = "level_change", Detail = $"{e.Previous}->{e.Current} by {e.Trigger}", Breakdown = BreakdownDict() });
            ApplyLevel(e.Current);
            LevelChanged?.Invoke(this, e);
            if (e.Current == RiskLevel.Critical)
                SessionLockRequested?.Invoke(this, "检测到自动化工具 / 异常操作,会话已锁定");
        }

        private void ApplyLevel(RiskLevel level)
        {
            UiaProbe.BlockUia = !Policy.AccessibilityMode && level >= RiskLevel.Elevated;
            foreach (var f in _protected.ToList())
            {
                if (f.IsDisposed) continue;
                try { f.BeginInvoke(new Action(() => f.Invalidate(true))); } catch { }
            }
        }

        private void OnDirective(object? sender, TelemetryResponse r)
        {
            switch (r.Directive)
            {
                case "lock":
                    Engine.Report(SignalKind.ServerDirective, 100, r.Message ?? "server lock");
                    break;
                case "degrade":
                    Engine.Report(SignalKind.ServerDirective, 65, r.Message ?? "server degrade");
                    break;
            }
            if (r.PolicyVersion.HasValue && r.PolicyVersion.Value != Policy.Version) _ = RefreshPolicyAsync();
        }

        internal void Emit(string type, GuardDecision d, string dataSet) => Emit(new GuardEvent
        {
            Type = type, Detail = $"{dataSet} {d.Operation} {d.Actions} rows<={d.RowLimit} :: {d.Reason}",
        });

        private void Emit(GuardEvent e)
        {
            e.TenantId = Options.TenantId;
            e.UserId = Options.UserId;
            e.DeviceId = DeviceId;
            e.SessionId = SessionId;
            e.Score = Engine.Score;
            e.Level = Engine.Level.ToString();
            e.ClientVersion = Options.ClientVersion;
            e.Os = Environment.OSVersion.VersionString;
            _sink.Enqueue(e);
        }

        private Dictionary<string, double> BreakdownDict() =>
            Engine.Breakdown().ToDictionary(kv => kv.Key.ToString(), kv => Math.Round(kv.Value, 1));

        private static string ComputeDeviceId()
        {
            var raw = Environment.MachineName + "|" + Environment.UserName + "|" + MacAddress();
            using var sha = SHA256.Create();
            var hash = sha.ComputeHash(Encoding.UTF8.GetBytes(raw));
            return BitConverter.ToString(hash, 0, 8).Replace("-", "").ToLowerInvariant();
        }

        private static string MacAddress()
        {
            try
            {
                return System.Net.NetworkInformation.NetworkInterface.GetAllNetworkInterfaces()
                    .Where(n => n.OperationalStatus == System.Net.NetworkInformation.OperationalStatus.Up &&
                                n.NetworkInterfaceType != System.Net.NetworkInformation.NetworkInterfaceType.Loopback)
                    .Select(n => n.GetPhysicalAddress().ToString())
                    .FirstOrDefault(m => !string.IsNullOrEmpty(m)) ?? "";
            }
            catch { return ""; }
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            _probeTimer.Dispose();
            _policyTimer.Dispose();
            _input?.Dispose();
            _clipboard.Dispose();
            UiaProbe.Dispose();
            Emit(new GuardEvent { Type = "heartbeat", Detail = "stop" });
            _sink.Dispose();
            _api?.Dispose();
            if (Current == this) Current = null;
        }
    }
}
