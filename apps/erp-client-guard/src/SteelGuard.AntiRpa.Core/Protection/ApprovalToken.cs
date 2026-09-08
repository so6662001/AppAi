using System;
using System.Globalization;
using System.Security.Cryptography;
using System.Text;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>审批 token 校验器抽象:本地 HMAC 校验 或 远程服务端校验。</summary>
    public interface IApprovalVerifier
    {
        ApprovalTokenVerifier.Result Verify(string token, string dataSet, int rowCount, DateTimeOffset now);
    }

    /// <summary>
    /// 审批 token 格式(与 client-guard-service 保持一致):
    /// <c>base64url(payload) "." base64url(HMAC-SHA256(payload))</c>
    /// payload = <c>tenant|user|dataset|maxRows|expiresUnix|approver|nonce</c>
    /// 注意:把 HMAC 密钥放客户端只适合"离线兜底"场景;生产建议用 <c>RemoteApprovalVerifier</c> 由服务端校验。
    /// </summary>
    public sealed class ApprovalTokenVerifier : IApprovalVerifier
    {
        private readonly byte[] _secret;
        private readonly long _tenantId;
        private readonly long _userId;

        public ApprovalTokenVerifier(string secret, long tenantId, long userId)
        {
            if (string.IsNullOrEmpty(secret)) throw new ArgumentException("secret required", nameof(secret));
            _secret = Encoding.UTF8.GetBytes(secret);
            _tenantId = tenantId;
            _userId = userId;
        }

        public sealed class Result
        {
            public bool Valid { get; set; }
            public string Error { get; set; } = "";
            public string Approver { get; set; } = "";
            public int MaxRows { get; set; }
            public DateTimeOffset ExpiresAt { get; set; }
        }

        public Result Verify(string token, string dataSet, int rowCount, DateTimeOffset now)
        {
            var r = new Result();
            if (string.IsNullOrWhiteSpace(token)) { r.Error = "empty"; return r; }
            var dot = token.IndexOf('.');
            if (dot <= 0 || dot == token.Length - 1) { r.Error = "format"; return r; }

            byte[] payloadBytes, sig;
            try
            {
                payloadBytes = Base64Url.Decode(token.Substring(0, dot));
                sig = Base64Url.Decode(token.Substring(dot + 1));
            }
            catch { r.Error = "base64"; return r; }

            using (var h = new HMACSHA256(_secret))
            {
                var expected = h.ComputeHash(payloadBytes);
                if (!FixedTimeEquals(expected, sig)) { r.Error = "signature"; return r; }
            }

            var parts = Encoding.UTF8.GetString(payloadBytes).Split('|');
            if (parts.Length < 7) { r.Error = "payload"; return r; }
            if (!long.TryParse(parts[0], out var t) || t != _tenantId) { r.Error = "tenant"; return r; }
            if (!long.TryParse(parts[1], out var u) || u != _userId) { r.Error = "user"; return r; }
            if (!string.Equals(parts[2], dataSet, StringComparison.OrdinalIgnoreCase)) { r.Error = "dataset"; return r; }
            if (!int.TryParse(parts[3], out var maxRows) || rowCount > maxRows) { r.Error = "rows"; return r; }
            if (!long.TryParse(parts[4], NumberStyles.Integer, CultureInfo.InvariantCulture, out var exp)) { r.Error = "expiry"; return r; }
            var expAt = DateTimeOffset.FromUnixTimeSeconds(exp);
            if (expAt < now) { r.Error = "expired"; return r; }

            r.Valid = true;
            r.Approver = parts[5];
            r.MaxRows = maxRows;
            r.ExpiresAt = expAt;
            return r;
        }

        /// <summary>签发(仅供测试 / 服务端参考实现;生产环境由服务端签发,密钥不下发客户端明文)。</summary>
        public static string Issue(string secret, long tenantId, long userId, string dataSet, int maxRows,
            DateTimeOffset expiresAt, string approver, string? nonce = null)
        {
            nonce ??= Guid.NewGuid().ToString("N").Substring(0, 8);
            var payload = string.Join("|", tenantId, userId, dataSet, maxRows,
                expiresAt.ToUnixTimeSeconds().ToString(CultureInfo.InvariantCulture), approver, nonce);
            var pb = Encoding.UTF8.GetBytes(payload);
            using var h = new HMACSHA256(Encoding.UTF8.GetBytes(secret));
            return Base64Url.Encode(pb) + "." + Base64Url.Encode(h.ComputeHash(pb));
        }

        private static bool FixedTimeEquals(byte[] a, byte[] b)
        {
            if (a.Length != b.Length) return false;
            int diff = 0;
            for (int i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
            return diff == 0;
        }
    }

    internal static class Base64Url
    {
        public static string Encode(byte[] data) =>
            Convert.ToBase64String(data).TrimEnd('=').Replace('+', '-').Replace('/', '_');

        public static byte[] Decode(string s)
        {
            var b = s.Replace('-', '+').Replace('_', '/');
            switch (b.Length % 4) { case 2: b += "=="; break; case 3: b += "="; break; }
            return Convert.FromBase64String(b);
        }
    }
}
