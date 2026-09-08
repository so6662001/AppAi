using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>水印上下文:谁、何时、哪台设备、哪次导出。</summary>
    public sealed class WatermarkContext
    {
        public long TenantId { get; set; }
        public long UserId { get; set; }
        public string UserName { get; set; } = "";
        public string DeviceId { get; set; } = "";
        public string ExportId { get; set; } = Guid.NewGuid().ToString("N").Substring(0, 12);
        public DateTimeOffset At { get; set; } = DateTimeOffset.Now;

        /// <summary>可见水印文本(放导出文件首行 / 页脚 / 网格背景)。</summary>
        public string VisibleText() =>
            $"导出:{UserName}({UserId}) {At.ToLocalTime():yyyy-MM-dd HH:mm} 设备 {Short(DeviceId)} 单号 {ExportId} · 内部资料 · 禁止外传";

        private static string Short(string s) => string.IsNullOrEmpty(s) ? "-" : (s.Length <= 6 ? s : s.Substring(0, 6));
    }

    /// <summary>
    /// 零宽字符隐形水印。
    /// 编码:起始标记 U+2060 (WORD JOINER) + 若干 bit(U+200B=0, U+200C=1) + 结束标记 U+200D。
    /// 载荷:<c>userId:exportId前8位:序号</c> 的 UTF-8 字节。
    /// 复制到 Excel / 微信 / 记事本后依旧保留,肉眼不可见;<see cref="Decode"/> 可还原。
    /// </summary>
    public static class Watermark
    {
        public const char ZeroBit = '\u200B';   // ZERO WIDTH SPACE
        public const char OneBit = '\u200C';    // ZERO WIDTH NON-JOINER
        public const char End = '\u200D';       // ZERO WIDTH JOINER
        public const char Start = '\u2060';     // WORD JOINER

        private static readonly char[] Markers = { ZeroBit, OneBit, End, Start };

        public static string Encode(string payload)
        {
            var bytes = Encoding.UTF8.GetBytes(payload);
            var sb = new StringBuilder(bytes.Length * 8 + 2);
            sb.Append(Start);
            foreach (var b in bytes)
                for (int i = 7; i >= 0; i--) sb.Append(((b >> i) & 1) == 1 ? OneBit : ZeroBit);
            sb.Append(End);
            return sb.ToString();
        }

        /// <summary>从任意文本中提取所有隐形水印载荷。</summary>
        public static IReadOnlyList<string> Decode(string text)
        {
            var result = new List<string>();
            if (string.IsNullOrEmpty(text)) return result;
            int i = 0;
            while ((i = text.IndexOf(Start, i)) >= 0)
            {
                i++;
                var bits = new List<byte>();
                int cur = 0, n = 0;
                bool ok = false;
                for (; i < text.Length; i++)
                {
                    var c = text[i];
                    if (c == ZeroBit || c == OneBit)
                    {
                        cur = (cur << 1) | (c == OneBit ? 1 : 0);
                        if (++n == 8) { bits.Add((byte)cur); cur = 0; n = 0; }
                    }
                    else if (c == End) { ok = n == 0; i++; break; }
                    else break;   // 被破坏
                }
                if (ok && bits.Count > 0)
                {
                    try { result.Add(Encoding.UTF8.GetString(bits.ToArray())); } catch { /* ignore */ }
                }
            }
            return result;
        }

        /// <summary>去掉所有零宽标记(用于展示前清洗 / 检测是否被剥离)。</summary>
        public static string Strip(string text) =>
            string.IsNullOrEmpty(text) ? text : new string(text.Where(c => Array.IndexOf(Markers, c) < 0).ToArray());

        /// <summary>在一个文本单元格中植入水印(插在首字符之后,避免影响排序/前缀匹配)。</summary>
        public static string Mark(string cell, WatermarkContext ctx, int seq)
        {
            if (string.IsNullOrEmpty(cell)) return cell;
            var payload = $"{ctx.UserId}:{ctx.ExportId.Substring(0, Math.Min(8, ctx.ExportId.Length))}:{seq}";
            var mark = Encode(payload);
            return cell.Length == 1 ? cell + mark : cell.Substring(0, 1) + mark + cell.Substring(1);
        }

        /// <summary>
        /// 对一批行(字典形式)按 <paramref name="everyNRows"/> 的间隔在首个非空文本列植入隐形水印,
        /// 同时返回带水印的副本;原集合不被修改。
        /// </summary>
        public static List<Dictionary<string, object?>> Apply(IEnumerable<Dictionary<string, object?>> rows,
            WatermarkContext ctx, IEnumerable<string>? preferredColumns = null, int everyNRows = 25)
        {
            if (everyNRows < 1) everyNRows = 1;
            var pref = (preferredColumns ?? Array.Empty<string>()).ToList();
            var output = new List<Dictionary<string, object?>>();
            int idx = 0, seq = 0;
            foreach (var row in rows)
            {
                var copy = new Dictionary<string, object?>(row);
                if (idx % everyNRows == 0)
                {
                    var col = pref.FirstOrDefault(c => copy.TryGetValue(c, out var v) && v is string s && s.Length > 0)
                              ?? copy.FirstOrDefault(kv => kv.Value is string s && s.Length > 0).Key;
                    if (col != null) copy[col] = Mark((string)copy[col]!, ctx, seq++);
                }
                output.Add(copy);
                idx++;
            }
            return output;
        }

        /// <summary>解析 Mark 载荷:userId / exportId 前缀 / 序号。</summary>
        public static bool TryParsePayload(string payload, out long userId, out string exportIdPrefix, out int seq)
        {
            userId = 0; exportIdPrefix = ""; seq = 0;
            var p = payload.Split(':');
            if (p.Length != 3) return false;
            if (!long.TryParse(p[0], NumberStyles.Integer, CultureInfo.InvariantCulture, out userId)) return false;
            exportIdPrefix = p[1];
            return int.TryParse(p[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out seq);
        }
    }
}
