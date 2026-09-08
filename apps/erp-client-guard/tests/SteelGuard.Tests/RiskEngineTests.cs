using System;
using System.Collections.Generic;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Risk;
using Xunit;

namespace SteelGuard.Tests
{
    public class RiskEngineTests
    {
        private static readonly DateTimeOffset T0 = new DateTimeOffset(2026, 9, 8, 9, 0, 0, TimeSpan.FromHours(8));

        [Fact]
        public void 单个RPA进程信号直接进入Elevated()
        {
            var clock = new ManualClock(T0);
            var e = new RiskEngine(GuardPolicy.Default, clock);
            e.Report(SignalKind.KnownAutomationProcess, "uirobot");
            Assert.Equal(40, e.Score, 1);
            Assert.Equal(RiskLevel.Elevated, e.Level);
        }

        [Fact]
        public void 同类信号受Cap限制_不会无限刷分()
        {
            var e = new RiskEngine(GuardPolicy.Default, new ManualClock(T0));
            for (int i = 0; i < 100; i++) e.Report(SignalKind.InjectedInput);
            Assert.Equal(40, e.Score, 1);   // cap = 40
            Assert.Equal(RiskLevel.Elevated, e.Level);
        }

        [Fact]
        public void 多信号叠加达到Critical并触发事件()
        {
            var e = new RiskEngine(GuardPolicy.Default, new ManualClock(T0));
            var changes = new List<(RiskLevel, RiskLevel)>();
            e.LevelChanged += (_, a) => changes.Add((a.Previous, a.Current));

            e.Report(SignalKind.KnownAutomationProcess);   // 40
            e.Report(SignalKind.UiaProbing);               // +25 = 65 High
            e.Report(SignalKind.RoboticTiming);            // +20 = 85 Critical

            Assert.Equal(RiskLevel.Critical, e.Level);
            Assert.Contains((RiskLevel.Low, RiskLevel.Elevated), changes);
            Assert.Contains((RiskLevel.Elevated, RiskLevel.High), changes);
            Assert.Contains((RiskLevel.High, RiskLevel.Critical), changes);
        }

        [Fact]
        public void 信号按半衰期指数衰减()
        {
            var clock = new ManualClock(T0);
            var e = new RiskEngine(GuardPolicy.Default, clock);
            e.Report(SignalKind.RoboticTiming);   // 20, half-life 300s
            Assert.Equal(20, e.Score, 1);
            clock.Advance(TimeSpan.FromSeconds(300));
            Assert.Equal(10, e.Score, 1);
            clock.Advance(TimeSpan.FromSeconds(600));
            Assert.Equal(2.5, e.Score, 1);
        }

        [Fact]
        public void 衰减后Reevaluate触发降级事件()
        {
            var clock = new ManualClock(T0);
            var e = new RiskEngine(GuardPolicy.Default, clock);
            RiskLevel? last = null;
            e.LevelChanged += (_, a) => last = a.Current;
            e.Report(SignalKind.KnownAutomationProcess);   // Elevated
            Assert.Equal(RiskLevel.Elevated, last);
            clock.Advance(TimeSpan.FromHours(2));
            e.Reevaluate();
            Assert.Equal(RiskLevel.Low, last);
        }

        [Fact]
        public void 远程会话中注入输入权重降低()
        {
            var e = new RiskEngine(GuardPolicy.Default, new ManualClock(T0)) { RemoteSession = true };
            for (int i = 0; i < 10; i++) e.Report(SignalKind.InjectedInput);
            Assert.Equal(10 * 3 * 0.2, e.Score, 1);
        }

        [Fact]
        public void 读屏软件在线时UIA信号归零()
        {
            var e = new RiskEngine(GuardPolicy.Default, new ManualClock(T0)) { AccessibilityToolPresent = true };
            e.Report(SignalKind.UiaProbing);
            e.Report(SignalKind.UiaCoreLoaded);
            Assert.Equal(0, e.Score, 3);
        }

        [Fact]
        public void 服务端策略JSON覆盖默认阈值与权重()
        {
            var json = @"{
              ""version"": 7,
              ""thresholds"": { ""elevated"": 20, ""high"": 50, ""critical"": 70 },
              ""weights"": { ""RoboticTiming"": { ""weight"": 50, ""half_life_sec"": 60, ""cap"": 50 } },
              ""automation_processes"": [""myrpa""],
              ""export_quota"": { ""max_rows_per_export"": 500 }
            }";
            var p = GuardPolicy.FromJson(json);
            Assert.Equal(7, p.Version);
            Assert.Equal(20, p.ElevatedThreshold);
            Assert.Equal(50, p.WeightOf(SignalKind.RoboticTiming).Weight);
            Assert.Equal(40, p.WeightOf(SignalKind.KnownAutomationProcess).Weight);   // 回落默认
            Assert.Contains("myrpa", p.AutomationProcesses);
            Assert.Equal(500, p.ExportQuota.MaxRowsPerExport);

            var e = new RiskEngine(p, new ManualClock(T0));
            e.Report(SignalKind.RoboticTiming);
            Assert.Equal(RiskLevel.High, e.Level);   // 50 >= high(50)
        }

        [Fact]
        public void 默认策略可往返序列化()
        {
            var json = GuardPolicy.Default.ToJson();
            var p = GuardPolicy.FromJson(json);
            Assert.Equal(GuardPolicy.Default.AutomationProcesses.Count, p.AutomationProcesses.Count);
            Assert.Equal(GuardPolicy.Default.WeightOf(SignalKind.UiaProbing).Cap, p.WeightOf(SignalKind.UiaProbing).Cap);
        }
    }
}
