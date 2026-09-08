using System;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Detection
{
    /// <summary>
    /// 低级键鼠钩子:读取 LLKHF_INJECTED / LLMHF_INJECTED 标志识别 SendInput / keybd_event / mouse_event 注入,
    /// 并把所有事件(含坐标)喂给 <see cref="BehaviorAnalyzer"/> 做节律 / 瞬移分析。
    /// 只处理"前台窗口属于本进程"的事件,避免误判用户在别的软件里的操作。
    /// 必须在有消息循环的 UI 线程上创建(WinForms 主线程)。
    /// </summary>
    public sealed class InputInjectionMonitor : IDisposable
    {
        private readonly BehaviorAnalyzer _analyzer;
        private readonly IGuardClock _clock;
        private IntPtr _kbHook = IntPtr.Zero;
        private IntPtr _mouseHook = IntPtr.Zero;
        // 必须持有委托引用,否则被 GC 回收后钩子崩溃
        private readonly NativeMethods.HookProc _kbProc;
        private readonly NativeMethods.HookProc _mouseProc;
        private readonly uint _pid = NativeMethods.GetCurrentProcessId();
        private long _moveSample;
        private bool _disposed;

        /// <summary>忽略非本进程前台窗口的事件(默认 true)。</summary>
        public bool OnlyWhenForeground { get; set; } = true;

        /// <summary>鼠标移动事件采样比例(每 N 条取 1 条,减轻负担)。</summary>
        public int MouseMoveSampling { get; set; } = 3;

        public long InjectedCount { get; private set; }
        public long TotalCount { get; private set; }

        public InputInjectionMonitor(BehaviorAnalyzer analyzer, IGuardClock? clock = null)
        {
            _analyzer = analyzer ?? throw new ArgumentNullException(nameof(analyzer));
            _clock = clock ?? SystemClock.Instance;
            _kbProc = KeyboardProc;
            _mouseProc = MouseProc;
        }

        public void Start()
        {
            if (_kbHook != IntPtr.Zero) return;
            var hMod = NativeMethods.GetModuleHandle(null);
            _kbHook = NativeMethods.SetWindowsHookEx(NativeMethods.WH_KEYBOARD_LL, _kbProc, hMod, 0);
            _mouseHook = NativeMethods.SetWindowsHookEx(NativeMethods.WH_MOUSE_LL, _mouseProc, hMod, 0);
            if (_kbHook == IntPtr.Zero || _mouseHook == IntPtr.Zero)
                throw new InvalidOperationException("SetWindowsHookEx failed: " + Marshal.GetLastWin32Error());
        }

        private bool IsOurForeground()
        {
            if (!OnlyWhenForeground) return true;
            var fg = NativeMethods.GetForegroundWindow();
            if (fg == IntPtr.Zero) return false;
            NativeMethods.GetWindowThreadProcessId(fg, out var pid);
            return pid == _pid;
        }

        private IntPtr KeyboardProc(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0)
            {
                try
                {
                    var msg = wParam.ToInt32();
                    if ((msg == NativeMethods.WM_KEYDOWN || msg == NativeMethods.WM_SYSKEYDOWN) && IsOurForeground())
                    {
                        var s = Marshal.PtrToStructure<NativeMethods.KBDLLHOOKSTRUCT>(lParam);
                        var injected = (s.flags & (NativeMethods.LLKHF_INJECTED | NativeMethods.LLKHF_LOWER_IL_INJECTED)) != 0;
                        TotalCount++;
                        if (injected) InjectedCount++;
                        _analyzer.Feed(new InputEvent(InputEventType.KeyDown, _clock.Now, 0, 0, injected));
                    }
                }
                catch { /* 钩子内绝不抛异常 */ }
            }
            return NativeMethods.CallNextHookEx(_kbHook, nCode, wParam, lParam);
        }

        private IntPtr MouseProc(int nCode, IntPtr wParam, IntPtr lParam)
        {
            if (nCode >= 0)
            {
                try
                {
                    var msg = wParam.ToInt32();
                    var isClick = msg == NativeMethods.WM_LBUTTONDOWN || msg == NativeMethods.WM_RBUTTONDOWN || msg == NativeMethods.WM_MBUTTONDOWN;
                    var isMove = msg == NativeMethods.WM_MOUSEMOVE;
                    if ((isClick || isMove) && IsOurForeground())
                    {
                        var s = Marshal.PtrToStructure<NativeMethods.MSLLHOOKSTRUCT>(lParam);
                        var injected = (s.flags & (NativeMethods.LLMHF_INJECTED | NativeMethods.LLMHF_LOWER_IL_INJECTED)) != 0;
                        if (isMove)
                        {
                            if (Interlocked.Increment(ref _moveSample) % Math.Max(1, MouseMoveSampling) != 0) goto next;
                            _analyzer.Feed(new InputEvent(InputEventType.MouseMove, _clock.Now, s.pt.x, s.pt.y, injected));
                        }
                        else
                        {
                            TotalCount++;
                            if (injected) InjectedCount++;
                            _analyzer.Feed(new InputEvent(InputEventType.MouseClick, _clock.Now, s.pt.x, s.pt.y, injected));
                        }
                    }
                }
                catch { /* ignore */ }
            }
        next:
            return NativeMethods.CallNextHookEx(_mouseHook, nCode, wParam, lParam);
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            if (_kbHook != IntPtr.Zero) { NativeMethods.UnhookWindowsHookEx(_kbHook); _kbHook = IntPtr.Zero; }
            if (_mouseHook != IntPtr.Zero) { NativeMethods.UnhookWindowsHookEx(_mouseHook); _mouseHook = IntPtr.Zero; }
        }
    }
}
