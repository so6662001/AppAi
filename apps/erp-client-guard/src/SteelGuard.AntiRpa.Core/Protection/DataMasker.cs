using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.RegularExpressions;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>
    /// 敏感列脱敏。按列名启发式选择脱敏方式:
    /// 手机号 138****1234;公司/人名 保留首字;金额/单价 保留量级(¥ 3***);银行卡 尾 4 位;其他 ***。
    /// </summary>
    public static class DataMasker
    {
        private static readonly Regex Phone = new Regex(@"^1\d{10}$", RegexOptions.Compiled);
        private static readonly Regex Digits = new Regex(@"^\d{8,}$", RegexOptions.Compiled);

        public static string Mask(string column, object? value)
        {
            if (value == null) return "";
            var s = value.ToString() ?? "";
            if (s.Length == 0) return s;
            var lc = column.ToLowerInvariant();

            if (lc.Contains("phone") || lc.Contains("mobile") || Phone.IsMatch(s))
                return s.Length >= 7 ? s.Substring(0, 3) + "****" + s.Substring(s.Length - 4) : "***";

            if (lc.Contains("bank") || lc.Contains("card") || lc.Contains("account"))
                return s.Length >= 4 ? "**** " + s.Substring(s.Length - 4) : "****";

            if (lc.Contains("name") || lc.Contains("contact") || lc.Contains("customer") || lc.Contains("supplier"))
                return s.Length <= 1 ? "*" : s.Substring(0, 1) + new string('*', Math.Min(6, Math.Max(2, s.Length - 1)));

            if (lc.Contains("price") || lc.Contains("amount") || lc.Contains("amt") || lc.Contains("profit") ||
                lc.Contains("cost") || lc.Contains("commission") || lc.Contains("credit"))
            {
                if (double.TryParse(s, out var d))
                {
                    var abs = Math.Abs(d);
                    if (abs < 1) return d < 0 ? "-0.**" : "0.**";
                    var magnitude = (int)Math.Floor(Math.Log10(abs));
                    var lead = (int)(abs / Math.Pow(10, magnitude));
                    return (d < 0 ? "-" : "") + lead + new string('*', magnitude);
                }
                return "***";
            }

            if (Digits.IsMatch(s)) return s.Substring(0, 2) + new string('*', s.Length - 4) + s.Substring(s.Length - 2);
            return s.Length <= 2 ? "**" : s.Substring(0, 1) + new string('*', Math.Min(6, s.Length - 1));
        }

        /// <summary>返回脱敏后的副本;原集合不被修改。</summary>
        public static List<Dictionary<string, object?>> MaskRows(IEnumerable<Dictionary<string, object?>> rows, IEnumerable<string> sensitiveColumns)
        {
            var set = new HashSet<string>(sensitiveColumns, StringComparer.OrdinalIgnoreCase);
            return rows.Select(r =>
            {
                var c = new Dictionary<string, object?>(r);
                foreach (var k in r.Keys.Where(set.Contains).ToList()) c[k] = Mask(k, r[k]);
                return c;
            }).ToList();
        }
    }
}
