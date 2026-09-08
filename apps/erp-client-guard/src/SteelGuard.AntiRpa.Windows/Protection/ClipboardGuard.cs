using System;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Protection
{
    /// <summary>
    /// 剪贴板监听:WM_CLIPBOARDUPDATE 计数(高频复制 → ClipboardBurst 信号)。
    /// 只统计本进程处于前台时发生的复制。不读取剪贴板内容。
    /// </summary>
    public sealed class ClipboardGuard : NativeWindow, IDisposable
    {
        private readonly BehaviorAnalyzer _analyzer;
        private readonly IGuardClock _clock;
        private readonly uint _pid = NativeMethods.GetCurrentProcessId();
        private bool _listening;

        public long CopyCount { get; private set; }

        public ClipboardGuard(BehaviorAnalyzer analyzer, IGuardClock? clock = null)
        {
            _analyzer = analyzer ?? throw new ArgumentNullException(nameof(analyzer));
            _clock = clock ?? SystemClock.Instance;
        }

        public void Start()
        {
            if (_listening) return;
            CreateHandle(new CreateParams { Caption = "SteelGuardClipboardSink", Parent = IntPtr.Zero, Style = 0, ExStyle = 0 });
            _listening = NativeMethods.AddClipboardFormatListener(Handle);
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == NativeMethods.WM_CLIPBOARDUPDATE)
            {
                try
                {
                    var fg = NativeMethods.GetForegroundWindow();
                    NativeMethods.GetWindowThreadProcessId(fg, out var pid);
                    if (pid == _pid)
                    {
                        CopyCount++;
                        _analyzer.Feed(new InputEvent(InputEventType.ClipboardCopy, _clock.Now));
                    }
                }
                catch { /* ignore */ }
            }
            base.WndProc(ref m);
        }

        public void Dispose()
        {
            if (_listening && Handle != IntPtr.Zero) NativeMethods.RemoveClipboardFormatListener(Handle);
            _listening = false;
            if (Handle != IntPtr.Zero) DestroyHandle();
        }
    }
}
