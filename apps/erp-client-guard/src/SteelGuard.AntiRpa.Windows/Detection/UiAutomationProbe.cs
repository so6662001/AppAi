using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Linq;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Detection
{
    /// <summary>
    /// UIA / MSAA 探针:
    /// 1. 子类化窗口,统计 WM_GETOBJECT 频率(RPA 选择器 / 抓取控件树时会高频发送);
    /// 2. 启动时记录基线,之后周期检查 UIAutomationCore.dll / oleacc.dll 是否被外部加载进本进程;
    /// 3. 可选:<see cref="BlockUia"/> 为 true 时对 UiaRootObjectId 请求返回 0,使 UIA 客户端看不到该窗口的控件树。
    /// </summary>
    public sealed class UiAutomationProbe : IDisposable
    {
        private readonly RiskEngine _engine;
        private readonly IGuardClock _clock;
        private readonly List<Subclass> _subclasses = new List<Subclass>();
        private readonly Queue<DateTimeOffset> _getObjectTimes = new Queue<DateTimeOffset>();
        private readonly object _lock = new object();
        private DateTimeOffset _lastFired = DateTimeOffset.MinValue;
        private bool _uiaCoreBaseline;
        private bool _uiaCoreReported;

        public long GetObjectCount { get; private set; }
        public long UiaRootRequests { get; private set; }

        /// <summary>对 UIA 根对象请求返回 0(隐藏控件树)。</summary>
        public bool BlockUia { get; set; }

        public UiAutomationProbe(RiskEngine engine, IGuardClock? clock = null)
        {
            _engine = engine ?? throw new ArgumentNullException(nameof(engine));
            _clock = clock ?? SystemClock.Instance;
            _uiaCoreBaseline = IsUiaCoreLoaded();
        }

        /// <summary>附加到窗体 / 控件(句柄创建后调用;句柄重建会自动重新附加)。</summary>
        public void Attach(Control control)
        {
            if (control == null) throw new ArgumentNullException(nameof(control));
            void Hook()
            {
                lock (_lock)
                {
                    if (_subclasses.Any(s => s.Owner == control && s.Handle == control.Handle)) return;
                    var sc = new Subclass(this, control);
                    sc.AssignHandle(control.Handle);
                    _subclasses.Add(sc);
                }
            }
            if (control.IsHandleCreated) Hook();
            control.HandleCreated += (_, __) => Hook();
            control.HandleDestroyed += (_, __) =>
            {
                lock (_lock)
                {
                    foreach (var s in _subclasses.Where(s => s.Owner == control).ToList())
                    {
                        s.ReleaseHandle();
                        _subclasses.Remove(s);
                    }
                }
            };
        }

        internal void OnGetObject(IntPtr lParam)
        {
            var objId = unchecked((int)lParam.ToInt64());
            var now = _clock.Now;
            lock (_lock)
            {
                GetObjectCount++;
                if (objId == NativeMethods.UiaRootObjectId) UiaRootRequests++;
                _getObjectTimes.Enqueue(now);
                while (_getObjectTimes.Count > 0 && (now - _getObjectTimes.Peek()).TotalSeconds > 60) _getObjectTimes.Dequeue();
                var perMin = _getObjectTimes.Count;
                var threshold = _engine.Policy.UiaProbePerMinute;
                if (perMin >= threshold && (now - _lastFired).TotalSeconds > 30)
                {
                    _lastFired = now;
                    var kind = objId == NativeMethods.UiaRootObjectId ? "UIA" : objId == NativeMethods.OBJID_CLIENT ? "MSAA" : $"objid={objId}";
                    _engine.Report(SignalKind.UiaProbing, $"{perMin} WM_GETOBJECT/min ({kind})");
                }
            }
        }

        /// <summary>周期调用(例如每 30s):检查 UIAutomationCore.dll 是否新出现。</summary>
        public void Poll()
        {
            if (_uiaCoreReported || _uiaCoreBaseline) return;
            if (IsUiaCoreLoaded())
            {
                _uiaCoreReported = true;
                _engine.Report(SignalKind.UiaCoreLoaded, "UIAutomationCore.dll loaded after startup");
            }
        }

        public static bool IsUiaCoreLoaded()
        {
            try
            {
                foreach (ProcessModule m in Process.GetCurrentProcess().Modules)
                {
                    var n = m.ModuleName?.ToLowerInvariant();
                    if (n == "uiautomationcore.dll") return true;
                }
            }
            catch { /* 权限不足等 */ }
            return false;
        }

        public void Dispose()
        {
            lock (_lock)
            {
                foreach (var s in _subclasses) s.ReleaseHandle();
                _subclasses.Clear();
            }
        }

        private sealed class Subclass : NativeWindow
        {
            private readonly UiAutomationProbe _owner;
            public Control Owner { get; }
            public Subclass(UiAutomationProbe owner, Control control) { _owner = owner; Owner = control; }

            protected override void WndProc(ref Message m)
            {
                if (m.Msg == NativeMethods.WM_GETOBJECT)
                {
                    _owner.OnGetObject(m.LParam);
                    if (_owner.BlockUia && unchecked((int)m.LParam.ToInt64()) == NativeMethods.UiaRootObjectId)
                    {
                        m.Result = IntPtr.Zero;   // 告诉 UIA:此窗口没有 provider
                        return;
                    }
                }
                else if (m.Msg == NativeMethods.WM_NCDESTROY)
                {
                    base.WndProc(ref m);
                    ReleaseHandle();
                    return;
                }
                base.WndProc(ref m);
            }
        }
    }
}
