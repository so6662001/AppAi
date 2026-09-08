using System;
using System.Collections.Generic;
using System.Linq;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Core.Protection
{
    /// <summary>一次导出请求的上下文。</summary>
    public sealed class ExportRequest
    {
        public string DataSet { get; set; } = "";
        public int RowCount { get; set; }
        public DataSensitivity Sensitivity { get; set; } = DataSensitivity.Internal;
        /// <summary>服务端签发的审批 token(若有)。</summary>
        public string? ApprovalToken { get; set; }
    }

    /// <summary>
    /// 导出治理:滑动窗口配额 + 单次上限 + 时间窗 + 审批 token 校验。
    /// 客户端侧配额只是"第一道门",服务端必须再做一遍(见 client-guard-service)。
    /// </summary>
    public sealed class ExportGovernor
    {
        private readonly IGuardClock _clock;
        private readonly object _lock = new object();
        private readonly List<(DateTimeOffset at, int rows)> _history = new List<(DateTimeOffset, int)>();
        private readonly RiskEngine _engine;

        public ExportGovernor(RiskEngine engine, IGuardClock? clock = null)
        {
            _engine = engine ?? throw new ArgumentNullException(nameof(engine));
            _clock = clock ?? SystemClock.Instance;
        }

        /// <summary>评估一次导出:合并策略决定 + 配额检查 + 审批 token 校验。</summary>
        public GuardDecision Evaluate(ExportRequest req, IApprovalVerifier? verifier = null, Random? rng = null)
        {
            if (req == null) throw new ArgumentNullException(nameof(req));
            var policy = _engine.Policy;
            var q = policy.ExportQuota;
            var now = _clock.Now;

            var d = PolicyEngine.Decide(policy, _engine.Level, _engine.Score, GuardOperation.Export, req.Sensitivity, req.RowCount, rng);
            if (!d.Allowed) return d;

            lock (_lock)
            {
                Prune(now);
                var lastHour = _history.Count(h => now - h.at <= TimeSpan.FromHours(1));
                var rowsToday = _history.Where(h => h.at.ToLocalTime().Date == now.ToLocalTime().Date).Sum(h => (long)h.rows);

                if (q.AllowedHours.Length > 0 && !q.AllowedHours.Contains(now.ToLocalTime().Hour))
                {
                    Deny(d, $"当前时段({now.ToLocalTime():HH:mm})不允许导出");
                    _engine.Report(SignalKind.ExportAnomaly, "export outside allowed hours");
                    return d;
                }
                if (lastHour >= q.MaxExportsPerHour)
                {
                    Deny(d, $"1 小时内导出次数已达上限 {q.MaxExportsPerHour} 次");
                    _engine.Report(SignalKind.ExportAnomaly, $"exports/hour={lastHour}");
                    return d;
                }
                if (rowsToday + Math.Min(req.RowCount, d.RowLimit) > q.MaxRowsPerDay)
                {
                    Deny(d, $"今日导出行数将超过上限 {q.MaxRowsPerDay:N0} 行");
                    _engine.Report(SignalKind.ExportAnomaly, $"rows/day={rowsToday}");
                    return d;
                }
            }

            if (d.RequiresApproval)
            {
                if (string.IsNullOrEmpty(req.ApprovalToken))
                {
                    // 保持 Allowed=false 但不是 Deny —— 由调用方去申请审批
                    d.Actions = (d.Actions & ~GuardAction.Allow) | GuardAction.RequireApproval;
                    d.Reason = "需要主管审批后导出";
                    return d;
                }
                if (verifier == null)
                {
                    Deny(d, "缺少审批校验器,无法验证 token");
                    return d;
                }
                var v = verifier.Verify(req.ApprovalToken!, req.DataSet, req.RowCount, now);
                if (!v.Valid)
                {
                    Deny(d, "审批 token 无效:" + v.Error);
                    _engine.Report(SignalKind.ExportAnomaly, "invalid approval token: " + v.Error);
                    return d;
                }
                d.Explanations.Add($"审批 token 有效,审批人 {v.Approver}");
            }
            return d;
        }

        /// <summary>导出成功后记录,用于配额统计。</summary>
        public void RecordExport(int rows)
        {
            lock (_lock)
            {
                _history.Add((_clock.Now, rows));
                Prune(_clock.Now);
            }
        }

        public (int exportsLastHour, long rowsToday) Usage()
        {
            lock (_lock)
            {
                var now = _clock.Now;
                Prune(now);
                return (_history.Count(h => now - h.at <= TimeSpan.FromHours(1)),
                        _history.Where(h => h.at.ToLocalTime().Date == now.ToLocalTime().Date).Sum(h => (long)h.rows));
            }
        }

        private void Prune(DateTimeOffset now) => _history.RemoveAll(h => now - h.at > TimeSpan.FromHours(48));

        private static void Deny(GuardDecision d, string reason)
        {
            d.Actions = (d.Actions & ~GuardAction.Allow) | GuardAction.Deny | GuardAction.Alert;
            d.Reason = reason;
        }
    }
}
