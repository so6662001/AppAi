using System;
using System.Collections.Generic;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>
    /// 启动票据:本地 RDP 启动器向服务端申请,随 StartProgram 命令行传给远程会话里的 ERP 客户端,
    /// ERP 用它调用 <c>/v1/session/bind</c> 完成双端绑定(共享 device_id / link_id)。
    /// 命令行形式:<c>erp.exe --guard-ticket=xxxx</c>
    /// </summary>
    public static class GuardTicket
    {
        public const string ArgName = "--guard-ticket";

        /// <summary>生成 StartProgram 命令行。</summary>
        public static string BuildCommandLine(string exePath, string ticket, string? extraArgs = null)
        {
            if (string.IsNullOrWhiteSpace(exePath)) throw new ArgumentException("exePath required", nameof(exePath));
            if (string.IsNullOrWhiteSpace(ticket)) throw new ArgumentException("ticket required", nameof(ticket));
            var exe = exePath.Contains(" ") && !exePath.StartsWith("\"") ? "\"" + exePath + "\"" : exePath;
            var s = exe + " " + ArgName + "=" + ticket;
            if (!string.IsNullOrWhiteSpace(extraArgs)) s += " " + extraArgs!.Trim();
            return s;
        }

        /// <summary>从进程命令行参数中解析票据;支持 <c>--guard-ticket=xxx</c> 与 <c>--guard-ticket xxx</c>。</summary>
        public static string? FromArgs(IEnumerable<string>? args)
        {
            if (args == null) return null;
            string? prev = null;
            foreach (var a in args)
            {
                if (a == null) continue;
                if (prev == ArgName) return a.Trim().Trim('"');
                if (a.StartsWith(ArgName + "=", StringComparison.OrdinalIgnoreCase))
                {
                    var v = a.Substring(ArgName.Length + 1).Trim().Trim('"');
                    return v.Length == 0 ? null : v;
                }
                prev = a;
            }
            return null;
        }
    }
}
