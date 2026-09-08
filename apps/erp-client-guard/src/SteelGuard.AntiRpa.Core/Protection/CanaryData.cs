using System;
using System.Collections.Generic;
using System.Linq;
using System.Security.Cryptography;
using System.Text;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>
    /// 蜜罐(金丝雀)行:按 HMAC(tenant, user, day) 确定性生成 1~3 条"看起来真实"的记录。
    /// 泄露文件里一旦出现这些记录,即可反查是哪个账号在哪天导出的。
    /// 生成器是确定性的,所以服务端不需要存每次导出的蜜罐,只要重算即可比对。
    /// </summary>
    public static class CanaryData
    {
        public sealed class Context
        {
            public long TenantId { get; set; }
            public long UserId { get; set; }
            public DateTimeOffset Day { get; set; } = DateTimeOffset.Now;
            public string Secret { get; set; } = "";
            public int Count { get; set; } = 2;
        }

        // 钢贸场景常见的公司名片段,组合出可信的假客户名
        private static readonly string[] Prefix = { "华", "鑫", "宝", "盛", "恒", "泰", "中", "金", "远", "隆", "顺", "瑞" };
        private static readonly string[] Middle = { "钢", "源", "达", "丰", "邦", "诚", "宏", "旺", "利", "润", "鼎", "冶" };
        private static readonly string[] Suffix = { "钢铁贸易有限公司", "金属材料有限公司", "物资有限公司", "钢材加工有限公司", "实业有限公司", "供应链有限公司" };
        private static readonly string[] Cities = { "上海", "天津", "唐山", "无锡", "佛山", "杭州", "郑州", "武汉", "成都", "沈阳", "乐从", "常州" };
        private static readonly string[] Grades = { "Q235B", "Q355B", "HRB400E", "SPCC", "DC01", "Q345B", "20#", "45#" };
        private static readonly string[] Specs = { "3.0*1500*C", "5.75*1500*C", "Φ12", "Φ16", "Φ20", "8*1500*6000", "2.0*1250*C", "10*2000*8000" };

        /// <summary>生成蜜罐行。列名与业务表对齐,不存在的列忽略。</summary>
        public static List<Dictionary<string, object?>> Generate(Context ctx, IEnumerable<string> columns)
        {
            if (ctx == null) throw new ArgumentNullException(nameof(ctx));
            var cols = columns.ToList();
            var list = new List<Dictionary<string, object?>>();
            for (int i = 0; i < Math.Max(1, ctx.Count); i++)
            {
                var seed = Seed(ctx, i);
                var rng = new DeterministicRandom(seed);
                var row = new Dictionary<string, object?>();
                var name = Cities[rng.Next(Cities.Length)] + Prefix[rng.Next(Prefix.Length)] + Middle[rng.Next(Middle.Length)] + Suffix[rng.Next(Suffix.Length)];
                var tag = ToBase32(seed).Substring(0, 6);

                foreach (var c in cols)
                {
                    var lc = c.ToLowerInvariant();
                    if (lc.Contains("customer") && lc.Contains("name")) row[c] = name;
                    else if (lc.Contains("supplier") && lc.Contains("name")) row[c] = name;
                    else if (lc.Contains("phone") || lc.Contains("mobile")) row[c] = "1" + (3 + rng.Next(6)) + rng.Digits(9);
                    else if (lc.Contains("order") && (lc.Contains("no") || lc.Contains("code"))) row[c] = "SO" + ctx.Day.ToString("yyMMdd") + tag;
                    else if (lc.Contains("grade") || lc.Contains("material")) row[c] = Grades[rng.Next(Grades.Length)];
                    else if (lc.Contains("spec")) row[c] = Specs[rng.Next(Specs.Length)];
                    else if (lc.Contains("ton") || lc.Contains("qty") || lc.Contains("weight")) row[c] = Math.Round(5 + rng.NextDouble() * 120, 3);
                    else if (lc.Contains("price")) row[c] = Math.Round(3300 + rng.NextDouble() * 1500, 0);
                    else if (lc.Contains("amount") || lc.Contains("amt")) row[c] = Math.Round(20000 + rng.NextDouble() * 400000, 2);
                    else if (lc.Contains("profit")) row[c] = Math.Round(-2000 + rng.NextDouble() * 12000, 2);
                    else if (lc.Contains("date") || lc.Contains("time")) row[c] = ctx.Day.AddDays(-rng.Next(20)).ToString("yyyy-MM-dd");
                    else if (lc.Contains("city") || lc.Contains("region") || lc.Contains("area")) row[c] = Cities[rng.Next(Cities.Length)];
                    else if (lc.Contains("id")) row[c] = 9_000_000 + rng.Next(900_000);
                    else if (lc.Contains("remark") || lc.Contains("memo") || lc.Contains("note")) row[c] = "";
                    else row[c] = null;
                }
                row["__canary"] = tag;   // 导出前由调用方移除此列;仅用于内部识别
                list.Add(row);
            }
            return list;
        }

        /// <summary>把蜜罐行随机(但确定性)插到真实数据中间,并移除内部标记列。</summary>
        public static List<Dictionary<string, object?>> Inject(IEnumerable<Dictionary<string, object?>> rows, Context ctx)
        {
            var real = rows.ToList();
            if (real.Count == 0) return real;
            var cols = real[0].Keys.ToList();
            var canaries = Generate(ctx, cols);
            var rng = new DeterministicRandom(Seed(ctx, 999));
            foreach (var c in canaries)
            {
                c.Remove("__canary");
                var pos = real.Count <= 2 ? real.Count : 1 + rng.Next(real.Count - 1);
                real.Insert(pos, c);
            }
            return real;
        }

        /// <summary>判断一条记录是否是某 (tenant,user,day) 的蜜罐(泄露溯源时使用)。</summary>
        public static bool Matches(Dictionary<string, object?> row, Context ctx, IEnumerable<string> keyColumns)
        {
            var keys = keyColumns.ToList();
            var canaries = Generate(ctx, row.Keys);
            return canaries.Any(c => keys.All(k =>
                row.TryGetValue(k, out var a) && c.TryGetValue(k, out var b) && string.Equals(a?.ToString(), b?.ToString(), StringComparison.Ordinal)));
        }

        private static byte[] Seed(Context ctx, int idx)
        {
            var msg = $"{ctx.TenantId}|{ctx.UserId}|{ctx.Day.ToLocalTime():yyyyMMdd}|{idx}";
            using var h = new HMACSHA256(Encoding.UTF8.GetBytes(ctx.Secret ?? ""));
            return h.ComputeHash(Encoding.UTF8.GetBytes(msg));
        }

        private static string ToBase32(byte[] data)
        {
            const string alphabet = "ABCDEFGHJKMNPQRSTVWXYZ23456789";
            var sb = new StringBuilder();
            foreach (var b in data) sb.Append(alphabet[b % alphabet.Length]);
            return sb.ToString();
        }

        /// <summary>基于种子字节的简易确定性随机数(xorshift)。</summary>
        private sealed class DeterministicRandom
        {
            private ulong _s;
            public DeterministicRandom(byte[] seed)
            {
                _s = BitConverter.ToUInt64(seed, 0) | 1UL;
            }
            private ulong NextU()
            {
                _s ^= _s << 13; _s ^= _s >> 7; _s ^= _s << 17;
                return _s;
            }
            public int Next(int maxExclusive) => maxExclusive <= 0 ? 0 : (int)(NextU() % (ulong)maxExclusive);
            public double NextDouble() => (NextU() >> 11) / (double)(1UL << 53);
            public string Digits(int n)
            {
                var sb = new StringBuilder(n);
                for (int i = 0; i < n; i++) sb.Append((char)('0' + Next(10)));
                return sb.ToString();
            }
        }
    }
}
