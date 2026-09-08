using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Windows
{
    /// <summary>服务端导出申请结果。</summary>
    public sealed class ExportRequestResult
    {
        /// <summary>approved / pending / denied</summary>
        [JsonPropertyName("status")] public string Status { get; set; } = "denied";
        [JsonPropertyName("request_id")] public string RequestId { get; set; } = "";
        [JsonPropertyName("token")] public string? Token { get; set; }
        [JsonPropertyName("message")] public string? Message { get; set; }
        [JsonPropertyName("approver")] public string? Approver { get; set; }
    }

    /// <summary>
    /// client-guard-service 客户端:策略拉取 / 导出申请 / token 远程校验。
    /// 所有方法都吞掉网络异常并返回 null / 拒绝,避免影响 ERP 主流程;调用方按"服务不可达 → 使用默认策略"处理。
    /// </summary>
    public sealed class GuardApiClient : IDisposable
    {
        private readonly HttpClient _http;
        private readonly string _base;
        private static readonly JsonSerializerOptions Json = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };

        public GuardApiClient(string endpoint, string? bearerToken, HttpMessageHandler? handler = null)
        {
            _base = endpoint.TrimEnd('/');
            _http = handler == null ? new HttpClient() : new HttpClient(handler);
            _http.Timeout = TimeSpan.FromSeconds(10);
            if (!string.IsNullOrEmpty(bearerToken))
                _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
        }

        public async Task<GuardPolicy?> FetchPolicyAsync(long tenantId, CancellationToken ct = default)
        {
            try
            {
                var s = await _http.GetStringAsync($"{_base}/policy?tenant_id={tenantId}").ConfigureAwait(false);
                return GuardPolicy.FromJson(s);
            }
            catch { return null; }
        }

        public async Task<ExportRequestResult?> RequestExportAsync(long tenantId, long userId, string dataSet, int rowCount,
            string deviceId, double riskScore, string reason, CancellationToken ct = default)
        {
            try
            {
                var body = JsonSerializer.Serialize(new
                {
                    tenant_id = tenantId, user_id = userId, data_set = dataSet, row_count = rowCount,
                    device_id = deviceId, risk_score = riskScore, reason,
                });
                using var content = new StringContent(body, Encoding.UTF8, "application/json");
                using var resp = await _http.PostAsync($"{_base}/export/request", content, ct).ConfigureAwait(false);
                var txt = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                if (!resp.IsSuccessStatusCode) return new ExportRequestResult { Status = "denied", Message = $"HTTP {(int)resp.StatusCode}: {txt}" };
                return JsonSerializer.Deserialize<ExportRequestResult>(txt, Json);
            }
            catch (Exception ex) { return new ExportRequestResult { Status = "denied", Message = "服务不可达: " + ex.Message }; }
        }

        public async Task<ExportRequestResult?> PollExportAsync(string requestId, CancellationToken ct = default)
        {
            try
            {
                var s = await _http.GetStringAsync($"{_base}/export/request/{Uri.EscapeDataString(requestId)}").ConfigureAwait(false);
                return JsonSerializer.Deserialize<ExportRequestResult>(s, Json);
            }
            catch { return null; }
        }

        public async Task<ApprovalTokenVerifier.Result> VerifyAsync(string token, string dataSet, int rowCount, CancellationToken ct = default)
        {
            try
            {
                var url = $"{_base}/export/verify?token={Uri.EscapeDataString(token)}&data_set={Uri.EscapeDataString(dataSet)}&row_count={rowCount}";
                var s = await _http.GetStringAsync(url).ConfigureAwait(false);
                using var doc = JsonDocument.Parse(s);
                var root = doc.RootElement;
                var r = new ApprovalTokenVerifier.Result { Valid = root.TryGetProperty("valid", out var v) && v.GetBoolean() };
                if (root.TryGetProperty("error", out var e) && e.ValueKind == JsonValueKind.String) r.Error = e.GetString() ?? "";
                if (root.TryGetProperty("approver", out var a) && a.ValueKind == JsonValueKind.String) r.Approver = a.GetString() ?? "";
                if (root.TryGetProperty("max_rows", out var m) && m.ValueKind == JsonValueKind.Number) r.MaxRows = m.GetInt32();
                return r;
            }
            catch (Exception ex) { return new ApprovalTokenVerifier.Result { Valid = false, Error = "verify unreachable: " + ex.Message }; }
        }

        public void Dispose() => _http.Dispose();
    }

    /// <summary>通过服务端校验审批 token(同步封装,供 ExportGovernor 使用)。</summary>
    public sealed class RemoteApprovalVerifier : IApprovalVerifier
    {
        private readonly GuardApiClient _api;
        public RemoteApprovalVerifier(GuardApiClient api) { _api = api; }
        public ApprovalTokenVerifier.Result Verify(string token, string dataSet, int rowCount, DateTimeOffset now) =>
            _api.VerifyAsync(token, dataSet, rowCount).GetAwaiter().GetResult();
    }
}
