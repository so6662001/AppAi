using System;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Protection
{
    /// <summary>
    /// 防截屏 / 防录屏:SetWindowDisplayAffinity。
    /// WDA_EXCLUDEFROMCAPTURE(Win10 2004+):窗口在截屏 / 录屏 / 远控画面中显示为黑块,本机显示正常。
    /// 老系统退化到 WDA_MONITOR(整体黑块)。
    /// 对图像识别类 RPA(影刀图像模式、Sikuli)与 Computer-Use 类 AI Agent 有效。
    /// </summary>
    public static class ScreenCaptureGuard
    {
        public static bool Apply(Form form, bool enable = true)
        {
            if (form == null) throw new ArgumentNullException(nameof(form));
            void Set()
            {
                if (!form.IsHandleCreated) return;
                var aff = enable ? NativeMethods.WDA_EXCLUDEFROMCAPTURE : NativeMethods.WDA_NONE;
                if (!NativeMethods.SetWindowDisplayAffinity(form.Handle, aff) && enable)
                    NativeMethods.SetWindowDisplayAffinity(form.Handle, NativeMethods.WDA_MONITOR);
            }
            if (form.IsHandleCreated) Set();
            form.HandleCreated += (_, __) => Set();
            return true;
        }

        public static bool IsSupported()
        {
            var v = Environment.OSVersion.Version;
            return v.Major > 10 || (v.Major == 10 && v.Build >= 19041);
        }
    }
}
