using System;
using System.Collections.Generic;

namespace SteelGuard.AntiRpa.Core.Risk
{
    /// <summary>策略引擎输出的动作。</summary>
    [Flags]
    public enum GuardAction
    {
        None = 0,
        /// <summary>允许操作。</summary>
        Allow = 1,
        /// <summary>需要附加可见 + 隐形水印。</summary>
        Watermark = 2,
        /// <summary>注入蜜罐行。</summary>
        Canary = 4,
        /// <summary>限制行数(见 <see cref="GuardDecision.RowLimit"/>)。</summary>
        LimitRows = 8,
        /// <summary>敏感列脱敏。</summary>
        Mask = 16,
        /// <summary>要求人机挑战(拖动验证 / 二次登录)。</summary>
        Challenge = 32,
        /// <summary>需要服务端审批 token。</summary>
        RequireApproval = 64,
        /// <summary>强制随机延迟。</summary>
        Delay = 128,
        /// <summary>隐藏 UIA 控件树。</summary>
        HideAccessibilityTree = 256,
        /// <summary>拒绝操作。</summary>
        Deny = 512,
        /// <summary>锁定会话,要求重新登录。</summary>
        LockSession = 1024,
        /// <summary>上报服务端告警。</summary>
        Alert = 2048,
    }

    /// <summary>针对一次受保护操作的决定。</summary>
    public sealed class GuardDecision
    {
        public GuardOperation Operation { get; set; }
        public RiskLevel Level { get; set; }
        public double Score { get; set; }
        public GuardAction Actions { get; set; }
        public bool Allowed => (Actions & GuardAction.Allow) != 0
                               && (Actions & GuardAction.Deny) == 0
                               && (Actions & GuardAction.LockSession) == 0;
        public bool RequiresChallenge => (Actions & GuardAction.Challenge) != 0;
        public bool RequiresApproval => (Actions & GuardAction.RequireApproval) != 0;
        /// <summary>允许的最大行数(0 = 不限)。</summary>
        public int RowLimit { get; set; }
        /// <summary>建议延迟毫秒数。</summary>
        public int DelayMs { get; set; }
        public string Reason { get; set; } = "";
        public List<string> Explanations { get; } = new List<string>();

        public bool Has(GuardAction a) => (Actions & a) == a;
        public override string ToString() => $"{Operation} @{Level}({Score:0}) => {Actions} rows<={RowLimit} :: {Reason}";
    }

    /// <summary>
    /// 把 (风险等级, 操作类型, 数据敏感级, 行数) 映射为动作集合。
    /// 规则是确定性的表驱动逻辑,便于审计与单测。
    /// </summary>
    public static class PolicyEngine
    {
        public static GuardDecision Decide(GuardPolicy policy, RiskLevel level, double score,
            GuardOperation op, DataSensitivity sensitivity = DataSensitivity.Internal, int rowCount = 0,
            Random? rng = null)
        {
            if (policy == null) throw new ArgumentNullException(nameof(policy));
            var d = new GuardDecision { Operation = op, Level = level, Score = score };
            var q = policy.ExportQuota;

            // ---------- Critical:一律拒绝 + 锁定 ----------
            if (level == RiskLevel.Critical)
            {
                d.Actions = GuardAction.Deny | GuardAction.LockSession | GuardAction.Alert | GuardAction.Mask | GuardAction.HideAccessibilityTree;
                d.Reason = "检测到自动化工具 / 异常操作,会话已锁定,请联系管理员";
                d.Explanations.Add($"风险分 {score:0} ≥ 临界阈值 {policy.CriticalThreshold:0}");
                return d;
            }

            switch (op)
            {
                case GuardOperation.View:
                    d.Actions = GuardAction.Allow;
                    if (level >= RiskLevel.Elevated && !policy.AccessibilityMode) d.Actions |= GuardAction.HideAccessibilityTree;
                    if (level >= RiskLevel.High && sensitivity >= DataSensitivity.Confidential) d.Actions |= GuardAction.Mask;
                    d.Reason = level >= RiskLevel.High ? "风险较高,敏感列已脱敏" : "允许";
                    break;

                case GuardOperation.Copy:
                    if (level >= RiskLevel.High)
                    {
                        d.Actions = GuardAction.Deny | GuardAction.Alert;
                        d.Reason = "当前风险较高,已禁用复制";
                    }
                    else
                    {
                        d.Actions = GuardAction.Allow | GuardAction.Watermark;
                        if (level == RiskLevel.Elevated || sensitivity >= DataSensitivity.Confidential)
                        {
                            d.Actions |= GuardAction.LimitRows;
                            d.RowLimit = level == RiskLevel.Elevated ? 50 : 200;
                        }
                        d.Reason = "允许复制" + (d.RowLimit > 0 ? $"(最多 {d.RowLimit} 行)" : "");
                    }
                    break;

                case GuardOperation.Export:
                case GuardOperation.Print:
                    d.Actions = GuardAction.Allow | GuardAction.Watermark;
                    if (sensitivity >= DataSensitivity.Confidential) d.Actions |= GuardAction.Canary;

                    var rowLimit = q.MaxRowsPerExport;
                    if (level == RiskLevel.Elevated) rowLimit = Math.Max(100, rowLimit / 2);
                    if (level == RiskLevel.High) rowLimit = Math.Max(100, rowLimit / 4);
                    d.RowLimit = rowLimit;
                    d.Actions |= GuardAction.LimitRows;

                    if (rowCount > 0 && rowCount > rowLimit)
                    {
                        d.Explanations.Add($"请求 {rowCount} 行 > 上限 {rowLimit} 行,将截断");
                    }

                    if (rowCount >= q.ApprovalThresholdRows || level >= RiskLevel.High)
                    {
                        d.Actions |= GuardAction.RequireApproval;
                        d.Explanations.Add(rowCount >= q.ApprovalThresholdRows
                            ? $"行数 {rowCount} ≥ 审批阈值 {q.ApprovalThresholdRows}"
                            : "风险等级 High,需审批");
                    }
                    if (level >= RiskLevel.High)
                    {
                        d.Actions |= GuardAction.Challenge | GuardAction.Alert;
                        if (sensitivity >= DataSensitivity.Confidential) d.Actions |= GuardAction.Mask;
                    }
                    if (level >= RiskLevel.Elevated || (q.DelayMaxMs > 0))
                    {
                        var min = level >= RiskLevel.Elevated ? Math.Max(2000, q.DelayMinMs) : q.DelayMinMs;
                        var max = level >= RiskLevel.Elevated ? Math.Max(5000, q.DelayMaxMs) : q.DelayMaxMs;
                        if (max > 0)
                        {
                            d.Actions |= GuardAction.Delay;
                            d.DelayMs = (rng ?? new Random()).Next(min, max + 1);
                        }
                    }
                    d.Reason = d.RequiresApproval ? "需要主管审批后导出" : d.RequiresChallenge ? "需要人工验证" : "允许导出";
                    break;
            }

            d.Explanations.Insert(0, $"风险等级 {level}(分值 {score:0})");
            return d;
        }
    }
}
