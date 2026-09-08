using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Core.Telemetry
{
    /// <summary>上报给服务端的事件(不包含任何屏幕内容 / 业务数据)。</summary>
    public sealed class GuardEvent
    {
        [JsonPropertyName("event_id")] public string EventId { get; set; } = Guid.NewGuid().ToString("N");
        [JsonPropertyName("tenant_id")] public long TenantId { get; set; }
        [JsonPropertyName("user_id")] public long UserId { get; set; }
        [JsonPropertyName("device_id")] public string DeviceId { get; set; } = "";
        [JsonPropertyName("session_id")] public string SessionId { get; set; } = "";
        [JsonPropertyName("at")] public DateTimeOffset At { get; set; } = DateTimeOffset.UtcNow;
        /// <summary>signal / decision / level_change / export / heartbeat</summary>
        [JsonPropertyName("type")] public string Type { get; set; } = "signal";
        [JsonPropertyName("kind")] public string? Kind { get; set; }
        [JsonPropertyName("weight")] public double? Weight { get; set; }
        [JsonPropertyName("score")] public double Score { get; set; }
        [JsonPropertyName("level")] public string Level { get; set; } = RiskLevel.Low.ToString();
        [JsonPropertyName("detail")] public string? Detail { get; set; }
        [JsonPropertyName("breakdown")] public Dictionary<string, double>? Breakdown { get; set; }
        [JsonPropertyName("client_version")] public string ClientVersion { get; set; } = "";
        [JsonPropertyName("os")] public string Os { get; set; } = "";
    }

    /// <summary>服务端对一批事件的回应:可下发指令。</summary>
    public sealed class TelemetryResponse
    {
        [JsonPropertyName("accepted")] public int Accepted { get; set; }
        /// <summary>none / degrade / lock</summary>
        [JsonPropertyName("directive")] public string Directive { get; set; } = "none";
        [JsonPropertyName("message")] public string? Message { get; set; }
        [JsonPropertyName("policy_version")] public int? PolicyVersion { get; set; }
    }

    public interface ITelemetrySink : IDisposable
    {
        void Enqueue(GuardEvent e);
        Task FlushAsync(CancellationToken ct = default);
        /// <summary>服务端下发指令时触发(仅 Http sink)。</summary>
        event EventHandler<TelemetryResponse>? DirectiveReceived;
    }

    /// <summary>写本地 JSON Lines(离线 / 调试)。</summary>
    public sealed class FileTelemetrySink : ITelemetrySink
    {
        private readonly string _path;
        private readonly ConcurrentQueue<GuardEvent> _q = new ConcurrentQueue<GuardEvent>();
        private readonly object _io = new object();
        public event EventHandler<TelemetryResponse>? DirectiveReceived { add { } remove { } }

        public FileTelemetrySink(string path) { _path = path; }

        public void Enqueue(GuardEvent e) => _q.Enqueue(e);

        public Task FlushAsync(CancellationToken ct = default)
        {
            lock (_io)
            {
                var dir = Path.GetDirectoryName(_path);
                if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);
                using var sw = new StreamWriter(_path, true, new UTF8Encoding(false));
                while (_q.TryDequeue(out var e)) sw.WriteLine(JsonSerializer.Serialize(e));
            }
            return Task.CompletedTask;
        }

        public void Dispose() => FlushAsync().GetAwaiter().GetResult();
    }

    /// <summary>
    /// HTTP 批量上报,带内存缓冲 + 指数退避重试 + 本地落盘兜底。
    /// 上报地址:<c>{endpoint}/events</c>。
    /// </summary>
    public sealed class HttpTelemetrySink : ITelemetrySink
    {
        private readonly HttpClient _http;
        private readonly string _endpoint;
        private readonly ConcurrentQueue<GuardEvent> _q = new ConcurrentQueue<GuardEvent>();
        private readonly Timer _timer;
        private readonly FileTelemetrySink? _fallback;
        private readonly SemaphoreSlim _flushing = new SemaphoreSlim(1, 1);
        private int _failures;
        private const int MaxBatch = 200;
        private const int MaxBuffered = 5000;

        public event EventHandler<TelemetryResponse>? DirectiveReceived;

        public HttpTelemetrySink(string endpoint, string? bearerToken, TimeSpan? interval = null, string? fallbackFile = null, HttpMessageHandler? handler = null)
        {
            _endpoint = endpoint.TrimEnd('/');
            _http = handler == null ? new HttpClient() : new HttpClient(handler);
            _http.Timeout = TimeSpan.FromSeconds(8);
            if (!string.IsNullOrEmpty(bearerToken))
                _http.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", bearerToken);
            if (fallbackFile != null) _fallback = new FileTelemetrySink(fallbackFile);
            var iv = interval ?? TimeSpan.FromSeconds(15);
            _timer = new Timer(state => { var ignored = FlushAsync(); }, null, iv, iv);
        }

        public void Enqueue(GuardEvent e)
        {
            _q.Enqueue(e);
            while (_q.Count > MaxBuffered && _q.TryDequeue(out var dropped)) _fallback?.Enqueue(dropped);
        }

        public async Task FlushAsync(CancellationToken ct = default)
        {
            if (!await _flushing.WaitAsync(0, ct).ConfigureAwait(false)) return;
            try
            {
                while (!_q.IsEmpty)
                {
                    var batch = new List<GuardEvent>(MaxBatch);
                    while (batch.Count < MaxBatch && _q.TryDequeue(out var e)) batch.Add(e);
                    if (batch.Count == 0) break;

                    try
                    {
                        var json = JsonSerializer.Serialize(batch);
                        using var content = new StringContent(json, Encoding.UTF8, "application/json");
                        using var resp = await _http.PostAsync(_endpoint + "/events", content, ct).ConfigureAwait(false);
                        if (!resp.IsSuccessStatusCode) throw new HttpRequestException("status " + (int)resp.StatusCode);
                        _failures = 0;
                        var body = await resp.Content.ReadAsStringAsync().ConfigureAwait(false);
                        if (!string.IsNullOrWhiteSpace(body))
                        {
                            var r = JsonSerializer.Deserialize<TelemetryResponse>(body);
                            if (r != null && r.Directive != "none") DirectiveReceived?.Invoke(this, r);
                        }
                    }
                    catch (Exception) when (!ct.IsCancellationRequested)
                    {
                        _failures++;
                        // 失败:退回队列头部(简单做法:重新入队),超过 5 次落盘
                        if (_failures > 5 && _fallback != null)
                        {
                            foreach (var e in batch) _fallback.Enqueue(e);
                            await _fallback.FlushAsync(ct).ConfigureAwait(false);
                            _failures = 0;
                        }
                        else
                        {
                            foreach (var e in batch) _q.Enqueue(e);
                        }
                        await Task.Delay(TimeSpan.FromSeconds(Math.Min(60, Math.Pow(2, _failures))), ct).ConfigureAwait(false);
                        break;
                    }
                }
            }
            finally { _flushing.Release(); }
        }

        public void Dispose()
        {
            _timer.Dispose();
            try { FlushAsync().Wait(TimeSpan.FromSeconds(5)); } catch { /* ignore */ }
            _fallback?.Dispose();
            _http.Dispose();
        }
    }
}
