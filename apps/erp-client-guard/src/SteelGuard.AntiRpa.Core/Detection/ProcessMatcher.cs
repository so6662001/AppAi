using System;
using System.Collections.Generic;
using System.Linq;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Core.Detection
{
    public enum ProcessCategory { None, Automation, RemoteControl, Accessibility }

    /// <summary>
    /// 进程名匹配(纯逻辑)。Windows 层负责枚举进程名,这里负责分类。
    /// 匹配规则:小写、去扩展名后,与名单做"相等 / 前缀+非字母边界 / 子串(名单项长度 ≥ 9)"。
    /// </summary>
    public sealed class ProcessMatcher
    {
        private readonly string[] _automation;
        private readonly string[] _remote;
        private readonly string[] _a11y;

        public ProcessMatcher(GuardPolicy policy)
        {
            if (policy == null) throw new ArgumentNullException(nameof(policy));
            _automation = Normalize(policy.AutomationProcesses);
            _remote = Normalize(policy.RemoteControlProcesses);
            _a11y = Normalize(policy.AccessibilityWhitelist);
        }

        public ProcessCategory Classify(string processName)
        {
            var n = NormalizeOne(processName);
            if (n.Length == 0) return ProcessCategory.None;
            if (Match(n, _a11y)) return ProcessCategory.Accessibility;
            if (Match(n, _automation)) return ProcessCategory.Automation;
            if (Match(n, _remote)) return ProcessCategory.RemoteControl;
            return ProcessCategory.None;
        }

        public IReadOnlyList<(string name, ProcessCategory category)> Scan(IEnumerable<string> processNames)
        {
            var result = new List<(string, ProcessCategory)>();
            foreach (var p in processNames.Distinct(StringComparer.OrdinalIgnoreCase))
            {
                var c = Classify(p);
                if (c != ProcessCategory.None) result.Add((p, c));
            }
            return result;
        }

        private static bool Match(string n, string[] list)
        {
            foreach (var item in list)
            {
                if (item.Length == 0) continue;
                if (n == item) return true;
                // 前缀 + 非字母边界:uipath.executor / autohotkey64 / todesk_service
                if (n.StartsWith(item, StringComparison.Ordinal) && !char.IsLetter(n[item.Length])) return true;
                // 足够长且独特的名字允许子串匹配:xxx-shadowbot-runner
                if (item.Length >= 9 && n.Contains(item)) return true;
            }
            return false;
        }

        private static string[] Normalize(IEnumerable<string> list) =>
            list.Select(NormalizeOne).Where(s => s.Length > 0).Distinct().ToArray();

        public static string NormalizeOne(string name)
        {
            if (string.IsNullOrWhiteSpace(name)) return "";
            var n = name.Trim().ToLowerInvariant();
            if (n.EndsWith(".exe", StringComparison.Ordinal)) n = n.Substring(0, n.Length - 4);
            return n;
        }
    }
}
