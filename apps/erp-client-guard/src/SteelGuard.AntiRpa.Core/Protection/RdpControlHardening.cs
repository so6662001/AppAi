using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>一次加固的结果(哪些设置生效、哪些因控件版本过旧不支持)。</summary>
    public sealed class HardeningReport
    {
        public List<string> Applied { get; } = new List<string>();
        public List<string> Failed { get; } = new List<string>();
        public bool ClipboardRedirected { get; set; }
        public bool DrivesRedirected { get; set; }
        public string? StartProgram { get; set; }
        public override string ToString() =>
            $"applied={Applied.Count} failed={Failed.Count} clipboard={ClipboardRedirected} drives={DrivesRedirected} start={StartProgram}";
    }

    /// <summary>
    /// 对 MsRdpClient ActiveX(MsTscAx.dll,CLSID_MsRdpClient9NotSafeForScripting = 8B918B82-7985-4C24-89DF-C33AD2BBFBCD)
    /// 做连接前加固。全部通过后期绑定(IDispatch)访问,SDK 不依赖 AxInterop.MSTSCLib,
    /// VB.NET / C# 宿主传入 <c>AxRdp.GetOcx()</c> 或直接传入 AxHost 控件即可。
    /// <para>
    /// 关键点:剪贴板 / 驱动器重定向决定了服务器里的数据能否"出来"。关掉后:
    /// 服务器上导出的 Excel 只能留在服务器(受服务端配额 / 审批 / 水印管控),
    /// 服务器里 Ctrl+C 的内容无法粘到本地。这些属性只能在 Connect 之前设置。
    /// </para>
    /// </summary>
    public static class RdpControlHardening
    {
        public const string Clsid_MsRdpClient9NotSafeForScripting = "8B918B82-7985-4C24-89DF-C33AD2BBFBCD";

        // 按新→旧尝试,兼容不同版本的 mstscax.dll
        private static readonly string[] AdvancedSettingsCandidates =
            { "AdvancedSettings9", "AdvancedSettings8", "AdvancedSettings7", "AdvancedSettings6", "AdvancedSettings5", "AdvancedSettings4", "AdvancedSettings3", "AdvancedSettings2" };
        private static readonly string[] SecuredSettingsCandidates = { "SecuredSettings3", "SecuredSettings2", "SecuredSettings" };

        /// <summary>
        /// 应用加固。<paramref name="allowClipboard"/> 由调用方按当前风险决定(策略 redirect_clipboard_when_low_risk)。
        /// </summary>
        public static HardeningReport Apply(object rdpControl, RdpHardening policy, bool allowClipboard,
            string? startProgram = null, string? workDir = null)
        {
            if (rdpControl == null) throw new ArgumentNullException(nameof(rdpControl));
            policy = policy ?? new RdpHardening();
            var ocx = Unwrap(rdpControl);
            var rep = new HardeningReport();

            var adv = FirstProperty(ocx, AdvancedSettingsCandidates, out var advName);
            if (adv == null)
            {
                rep.Failed.Add("AdvancedSettings*: not found (not an MsRdpClient control?)");
            }
            else
            {
                var clip = policy.RedirectClipboard || (allowClipboard && policy.RedirectClipboardWhenLowRisk);
                Set(adv, advName!, "RedirectClipboard", clip, rep);
                Set(adv, advName!, "RedirectDrives", policy.RedirectDrives, rep);
                Set(adv, advName!, "RedirectPrinters", policy.RedirectPrinters, rep);
                Set(adv, advName!, "RedirectSmartCards", policy.RedirectSmartCards, rep);
                Set(adv, advName!, "RedirectPorts", policy.RedirectPorts, rep);
                Set(adv, advName!, "RedirectDevices", policy.RedirectDevices, rep);
                Set(adv, advName!, "RedirectPOSDevices", false, rep);
                // 认证加固:CredSSP + 服务器身份验证
                Set(adv, advName!, "EnableCredSspSupport", true, rep);
                Set(adv, advName!, "AuthenticationLevel", 2u, rep);
                // 会话内不弹"连接栏"(减少用户误触全屏切换,和防护无直接关系,可失败)
                Set(adv, advName!, "DisplayConnectionBar", false, rep);

                rep.ClipboardRedirected = ReadBool(adv, "RedirectClipboard", clip);
                rep.DrivesRedirected = ReadBool(adv, "RedirectDrives", policy.RedirectDrives);
            }

            // 非脚本接口(IMsRdpClientNonScriptable3):即插即用盘 / 设备,后期绑定通常拿不到,尽力而为
            TrySetDirect(ocx, "RedirectDynamicDrives", policy.RedirectDynamicDrives, rep);
            TrySetDirect(ocx, "RedirectDynamicDevices", policy.RedirectDevices, rep);
            TrySetDirect(ocx, "WarnAboutClipboardRedirection", false, rep);

            if (policy.StartProgramOnly && !string.IsNullOrWhiteSpace(startProgram))
            {
                var sec = FirstProperty(ocx, SecuredSettingsCandidates, out var secName);
                if (sec == null) rep.Failed.Add("SecuredSettings*: not found");
                else
                {
                    Set(sec, secName!, "StartProgram", startProgram!, rep);
                    if (!string.IsNullOrWhiteSpace(workDir)) Set(sec, secName!, "WorkDir", workDir!, rep);
                    rep.StartProgram = startProgram;
                }
            }
            return rep;
        }

        /// <summary>连接后复核:确认剪贴板 / 驱动器重定向确实是关闭状态(防止宿主代码在别处又打开)。</summary>
        public static bool VerifyLockedDown(object rdpControl, RdpHardening policy, bool allowClipboard)
        {
            var ocx = Unwrap(rdpControl);
            var adv = FirstProperty(ocx, AdvancedSettingsCandidates, out _);
            if (adv == null) return false;
            var clipExpected = policy.RedirectClipboard || (allowClipboard && policy.RedirectClipboardWhenLowRisk);
            var clip = ReadBool(adv, "RedirectClipboard", !clipExpected);
            var drives = ReadBool(adv, "RedirectDrives", !policy.RedirectDrives);
            return clip == clipExpected && drives == policy.RedirectDrives;
        }

        /// <summary>断开连接(风险达到阈值时由启动器调用)。</summary>
        public static bool Disconnect(object rdpControl)
        {
            try
            {
                var ocx = Unwrap(rdpControl);
                if (ConnectionState(ocx) == 0) return true;
                ocx.GetType().InvokeMember("Disconnect", BindingFlags.InvokeMethod | BindingFlags.Public | BindingFlags.Instance, null, ocx, null);
                return true;
            }
            catch { return false; }
        }

        /// <summary>0 = 未连接,1 = 已连接,2 = 连接中。读不到时返回 -1。</summary>
        public static int ConnectionState(object rdpControl)
        {
            try
            {
                var ocx = Unwrap(rdpControl);
                var v = ocx.GetType().InvokeMember("Connected", BindingFlags.GetProperty | BindingFlags.Public | BindingFlags.Instance, null, ocx, null);
                return v == null ? -1 : Convert.ToInt32(v, CultureInfo.InvariantCulture);
            }
            catch { return -1; }
        }

        // ------------------------------------------------------------------
        /// <summary>传入 AxHost(有 GetOcx() 方法)时取其 OCX;否则原样返回。Core 不引用 WinForms,按鸭子类型处理。</summary>
        public static object Unwrap(object control)
        {
            var m = control.GetType().GetMethod("GetOcx", BindingFlags.Public | BindingFlags.Instance, null, Type.EmptyTypes, null);
            if (m == null) return control;
            var ocx = m.Invoke(control, null);
            if (ocx == null) throw new InvalidOperationException("AxHost 尚未创建 OCX(需先加入窗体并创建句柄)");
            return ocx;
        }

        private static object? FirstProperty(object target, string[] names, out string? used)
        {
            foreach (var n in names)
            {
                try
                {
                    var v = target.GetType().InvokeMember(n, BindingFlags.GetProperty | BindingFlags.Public | BindingFlags.Instance, null, target, null);
                    if (v != null) { used = n; return v; }
                }
                catch { /* 该版本无此属性 */ }
            }
            used = null;
            return null;
        }

        private static void Set(object target, string owner, string name, object value, HardeningReport rep)
        {
            try
            {
                target.GetType().InvokeMember(name, BindingFlags.SetProperty | BindingFlags.Public | BindingFlags.Instance, null, target, new[] { value });
                rep.Applied.Add($"{owner}.{name}={value}");
            }
            catch (Exception ex)
            {
                rep.Failed.Add($"{owner}.{name}: {Root(ex).Message}");
            }
        }

        private static void TrySetDirect(object target, string name, object value, HardeningReport rep)
        {
            try
            {
                target.GetType().InvokeMember(name, BindingFlags.SetProperty | BindingFlags.Public | BindingFlags.Instance, null, target, new[] { value });
                rep.Applied.Add($"{name}={value}");
            }
            catch { /* 非脚本接口在 IDispatch 上不可见,属正常 */ }
        }

        private static bool ReadBool(object target, string name, bool fallback)
        {
            try
            {
                var v = target.GetType().InvokeMember(name, BindingFlags.GetProperty | BindingFlags.Public | BindingFlags.Instance, null, target, null);
                return v == null ? fallback : Convert.ToBoolean(v, CultureInfo.InvariantCulture);
            }
            catch { return fallback; }
        }

        private static Exception Root(Exception ex)
        {
            while (ex.InnerException != null) ex = ex.InnerException;
            return ex;
        }
    }
}
