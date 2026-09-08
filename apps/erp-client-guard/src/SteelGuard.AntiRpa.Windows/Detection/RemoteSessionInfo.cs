using System;
using System.Runtime.InteropServices;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Detection
{
    /// <summary>
    /// 远程会话信息(在 RDS 服务器会话内运行时可用):连接进来的 RDP 客户机名 / 地址 / 协议 / 初始程序。
    /// 用于把远程会话与本地启动器绑定(无 ticket 时按客户机名兜底匹配)。
    /// </summary>
    public sealed class RemoteSessionInfo
    {
        public bool IsRemote { get; private set; }
        public string ClientName { get; private set; } = "";
        public string ClientAddress { get; private set; } = "";
        /// <summary>0 = console, 1 = ICA(Citrix), 2 = RDP</summary>
        public int ProtocolType { get; private set; }
        public string InitialProgram { get; private set; } = "";
        public string WinStationName { get; private set; } = "";
        public int SessionId { get; private set; }

        public static RemoteSessionInfo Query()
        {
            var r = new RemoteSessionInfo
            {
                IsRemote = NativeMethods.GetSystemMetrics(NativeMethods.SM_REMOTESESSION) != 0,
            };
            try
            {
                r.ClientName = QueryString(NativeMethods.WTS_INFO_CLASS.WTSClientName);
                r.WinStationName = QueryString(NativeMethods.WTS_INFO_CLASS.WTSWinStationName);
                r.InitialProgram = QueryString(NativeMethods.WTS_INFO_CLASS.WTSInitialProgram);
                r.ProtocolType = QueryUInt16(NativeMethods.WTS_INFO_CLASS.WTSClientProtocolType);
                r.SessionId = (int)QueryUInt32(NativeMethods.WTS_INFO_CLASS.WTSSessionId);
                r.ClientAddress = QueryClientAddress();
            }
            catch { /* 非 RDS 环境 / 权限不足 */ }
            return r;
        }

        private static string QueryString(NativeMethods.WTS_INFO_CLASS cls)
        {
            if (!NativeMethods.WTSQuerySessionInformation(NativeMethods.WTS_CURRENT_SERVER_HANDLE, NativeMethods.WTS_CURRENT_SESSION, cls, out var p, out var n) || p == IntPtr.Zero)
                return "";
            try { return Marshal.PtrToStringUni(p) ?? ""; }
            finally { NativeMethods.WTSFreeMemory(p); }
        }

        private static ushort QueryUInt16(NativeMethods.WTS_INFO_CLASS cls)
        {
            if (!NativeMethods.WTSQuerySessionInformation(NativeMethods.WTS_CURRENT_SERVER_HANDLE, NativeMethods.WTS_CURRENT_SESSION, cls, out var p, out var n) || p == IntPtr.Zero)
                return 0;
            try { return n >= 2 ? (ushort)Marshal.ReadInt16(p) : (ushort)0; }
            finally { NativeMethods.WTSFreeMemory(p); }
        }

        private static uint QueryUInt32(NativeMethods.WTS_INFO_CLASS cls)
        {
            if (!NativeMethods.WTSQuerySessionInformation(NativeMethods.WTS_CURRENT_SERVER_HANDLE, NativeMethods.WTS_CURRENT_SESSION, cls, out var p, out var n) || p == IntPtr.Zero)
                return 0;
            try { return n >= 4 ? (uint)Marshal.ReadInt32(p) : 0u; }
            finally { NativeMethods.WTSFreeMemory(p); }
        }

        /// <summary>WTS_CLIENT_ADDRESS: DWORD AddressFamily + BYTE Address[20](IPv4 在 Address[2..5])。</summary>
        private static string QueryClientAddress()
        {
            if (!NativeMethods.WTSQuerySessionInformation(NativeMethods.WTS_CURRENT_SERVER_HANDLE, NativeMethods.WTS_CURRENT_SESSION, NativeMethods.WTS_INFO_CLASS.WTSClientAddress, out var p, out var n) || p == IntPtr.Zero)
                return "";
            try
            {
                if (n < 24) return "";
                var family = Marshal.ReadInt32(p);
                if (family == 2)   // AF_INET
                    return $"{Marshal.ReadByte(p, 6)}.{Marshal.ReadByte(p, 7)}.{Marshal.ReadByte(p, 8)}.{Marshal.ReadByte(p, 9)}";
                return "";
            }
            finally { NativeMethods.WTSFreeMemory(p); }
        }
    }
}
