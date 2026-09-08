using System;
using System.Runtime.InteropServices;

namespace SteelGuard.AntiRpa.Windows.Native
{
    internal static class NativeMethods
    {
        // ---------------- Hooks ----------------
        public const int WH_KEYBOARD_LL = 13;
        public const int WH_MOUSE_LL = 14;

        public const int WM_KEYDOWN = 0x0100;
        public const int WM_SYSKEYDOWN = 0x0104;
        public const int WM_MOUSEMOVE = 0x0200;
        public const int WM_LBUTTONDOWN = 0x0201;
        public const int WM_RBUTTONDOWN = 0x0204;
        public const int WM_MBUTTONDOWN = 0x0207;
        public const int WM_GETOBJECT = 0x003D;
        public const int WM_CLIPBOARDUPDATE = 0x031D;
        public const int WM_NCDESTROY = 0x0082;

        // KBDLLHOOKSTRUCT.flags
        public const uint LLKHF_LOWER_IL_INJECTED = 0x02;
        public const uint LLKHF_INJECTED = 0x10;
        // MSLLHOOKSTRUCT.flags
        public const uint LLMHF_INJECTED = 0x01;
        public const uint LLMHF_LOWER_IL_INJECTED = 0x02;

        // WM_GETOBJECT lParam
        public const int OBJID_CLIENT = -4;
        public const int OBJID_WINDOW = 0;
        public const int UiaRootObjectId = -25;

        // SetWindowDisplayAffinity
        public const uint WDA_NONE = 0x0;
        public const uint WDA_MONITOR = 0x1;
        public const uint WDA_EXCLUDEFROMCAPTURE = 0x11;

        public const int SM_REMOTESESSION = 0x1000;

        public delegate IntPtr HookProc(int nCode, IntPtr wParam, IntPtr lParam);

        [StructLayout(LayoutKind.Sequential)]
        public struct KBDLLHOOKSTRUCT
        {
            public uint vkCode;
            public uint scanCode;
            public uint flags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int x; public int y; }

        [StructLayout(LayoutKind.Sequential)]
        public struct MSLLHOOKSTRUCT
        {
            public POINT pt;
            public uint mouseData;
            public uint flags;
            public uint time;
            public IntPtr dwExtraInfo;
        }

        [DllImport("user32.dll", SetLastError = true)]
        public static extern IntPtr SetWindowsHookEx(int idHook, HookProc lpfn, IntPtr hMod, uint dwThreadId);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool UnhookWindowsHookEx(IntPtr hhk);

        [DllImport("user32.dll")]
        public static extern IntPtr CallNextHookEx(IntPtr hhk, int nCode, IntPtr wParam, IntPtr lParam);

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        public static extern IntPtr GetModuleHandle(string? lpModuleName);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool SetWindowDisplayAffinity(IntPtr hWnd, uint dwAffinity);

        [DllImport("user32.dll")]
        public static extern int GetSystemMetrics(int nIndex);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool AddClipboardFormatListener(IntPtr hwnd);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool RemoveClipboardFormatListener(IntPtr hwnd);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool CheckRemoteDebuggerPresent(IntPtr hProcess, [MarshalAs(UnmanagedType.Bool)] ref bool isDebuggerPresent);

        [DllImport("kernel32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool IsDebuggerPresent();

        [DllImport("kernel32.dll")]
        public static extern IntPtr GetCurrentProcess();

        [DllImport("user32.dll")]
        public static extern IntPtr GetForegroundWindow();

        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

        [DllImport("kernel32.dll")]
        public static extern uint GetCurrentProcessId();

        [DllImport("user32.dll")]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool ReleaseCapture();

        // ---------------- WTS (远程会话信息) ----------------
        public static readonly IntPtr WTS_CURRENT_SERVER_HANDLE = IntPtr.Zero;
        public const int WTS_CURRENT_SESSION = -1;

        public enum WTS_INFO_CLASS
        {
            WTSInitialProgram = 0, WTSApplicationName = 1, WTSWorkingDirectory = 2, WTSOEMId = 3, WTSSessionId = 4,
            WTSUserName = 5, WTSWinStationName = 6, WTSDomainName = 7, WTSConnectState = 8, WTSClientBuildNumber = 9,
            WTSClientName = 10, WTSClientDirectory = 11, WTSClientProductId = 12, WTSClientHardwareId = 13,
            WTSClientAddress = 14, WTSClientDisplay = 15, WTSClientProtocolType = 16,
        }

        [DllImport("wtsapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        public static extern bool WTSQuerySessionInformation(IntPtr hServer, int sessionId, WTS_INFO_CLASS infoClass,
            out IntPtr ppBuffer, out uint pBytesReturned);

        [DllImport("wtsapi32.dll")]
        public static extern void WTSFreeMemory(IntPtr pMemory);
    }
}
