using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using Microsoft.Win32;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Detection
{
    /// <summary>
    /// 环境与进程探针(周期运行,建议 20~60s):
    /// - 已知 RPA / AI Agent / 远控进程扫描(只读进程名,不读内存);
    /// - RDP 会话;调试器;虚拟机(弱信号)。
    /// 每个发现只在"首次出现"时上报一次,进程消失后重新计数。
    /// </summary>
    public sealed class EnvironmentProbe
    {
        private readonly RiskEngine _engine;
        private ProcessMatcher _matcher;
        private readonly HashSet<string> _reported = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private bool _rdpReported, _dbgReported, _vmReported;

        public IReadOnlyCollection<string> DetectedAutomation => _reported.Where(r => r.StartsWith("A:")).Select(r => r.Substring(2)).ToList();

        public EnvironmentProbe(RiskEngine engine)
        {
            _engine = engine ?? throw new ArgumentNullException(nameof(engine));
            _matcher = new ProcessMatcher(engine.Policy);
        }

        public void UpdatePolicy(GuardPolicy policy) => _matcher = new ProcessMatcher(policy);

        /// <summary>清空"已上报"记忆,下一次 Poll 会把仍在运行的可疑进程重新上报(风险引擎 Reset 后调用)。</summary>
        public void ResetReported()
        {
            _reported.Clear();
            _rdpReported = _dbgReported = false;
        }

        public void Poll()
        {
            PollProcesses();
            PollSession();
            PollDebugger();
            PollVm();
        }

        /// <summary>
        /// 枚举进程名。默认只看 *当前登录会话* 的进程:RDS / 终端服务器上多个用户共用一台机器,
        /// 不能因为别的会话里有人跑 RPA 就把本用户判为高风险。
        /// </summary>
        public static IEnumerable<string> EnumerateProcessNames(bool currentSessionOnly = true)
        {
            Process[] ps;
            int mySession;
            try
            {
                ps = Process.GetProcesses();
                mySession = Process.GetCurrentProcess().SessionId;
            }
            catch { yield break; }
            foreach (var p in ps)
            {
                string? n = null;
                try
                {
                    if (!currentSessionOnly || p.SessionId == mySession) n = p.ProcessName;
                }
                catch { /* 已退出 / 无权限 */ }
                finally { p.Dispose(); }
                if (!string.IsNullOrEmpty(n)) yield return n!;
            }
        }

        /// <summary>是否只扫描当前会话的进程(默认 true)。</summary>
        public bool CurrentSessionOnly { get; set; } = true;

        private void PollProcesses()
        {
            var names = EnumerateProcessNames(CurrentSessionOnly).ToList();
            var hits = _matcher.Scan(names);
            var present = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

            _engine.AccessibilityToolPresent = hits.Any(h => h.category == ProcessCategory.Accessibility);

            foreach (var (name, cat) in hits)
            {
                var key = (cat == ProcessCategory.Automation ? "A:" : cat == ProcessCategory.RemoteControl ? "R:" : "X:") + name;
                present.Add(key);
                if (_reported.Contains(key)) continue;
                _reported.Add(key);
                switch (cat)
                {
                    case ProcessCategory.Automation:
                        _engine.Report(SignalKind.KnownAutomationProcess, name);
                        break;
                    case ProcessCategory.RemoteControl:
                        _engine.Report(SignalKind.RemoteControlProcess, name);
                        break;
                }
            }
            // 进程退出后允许再次上报
            _reported.RemoveWhere(k => !present.Contains(k));
        }

        private void PollSession()
        {
            var remote = NativeMethods.GetSystemMetrics(NativeMethods.SM_REMOTESESSION) != 0;
            _engine.RemoteSession = remote;
            if (remote && !_rdpReported)
            {
                _rdpReported = true;
                _engine.Report(SignalKind.RemoteSession, "SM_REMOTESESSION");
            }
        }

        private void PollDebugger()
        {
            if (_dbgReported) return;
            bool remote = false;
            var attached = Debugger.IsAttached || NativeMethods.IsDebuggerPresent();
            try { NativeMethods.CheckRemoteDebuggerPresent(NativeMethods.GetCurrentProcess(), ref remote); } catch { }
            if (attached || remote)
            {
                _dbgReported = true;
                _engine.Report(SignalKind.DebuggerAttached, attached ? "IsDebuggerPresent" : "CheckRemoteDebuggerPresent");
            }
        }

        private void PollVm()
        {
            if (_vmReported) return;
            _vmReported = true;   // 只查一次
            try
            {
                using var key = Registry.LocalMachine.OpenSubKey(@"HARDWARE\DESCRIPTION\System\BIOS");
                var mfr = (key?.GetValue("SystemManufacturer") as string ?? "") + " " + (key?.GetValue("SystemProductName") as string ?? "");
                var l = mfr.ToLowerInvariant();
                if (l.Contains("vmware") || l.Contains("virtualbox") || l.Contains("qemu") || l.Contains("kvm") ||
                    l.Contains("hyper-v") || l.Contains("virtual machine") || l.Contains("xen") || l.Contains("parallels"))
                    _engine.Report(SignalKind.VirtualMachine, mfr.Trim());
            }
            catch { /* ignore */ }
        }
    }
}
