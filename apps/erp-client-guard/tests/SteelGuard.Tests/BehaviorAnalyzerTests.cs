using System;
using System.Collections.Generic;
using System.Linq;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Core.Risk;
using Xunit;

namespace SteelGuard.Tests
{
    public class BehaviorAnalyzerTests
    {
        private static readonly DateTimeOffset T0 = new DateTimeOffset(2026, 9, 8, 9, 0, 0, TimeSpan.FromHours(8));

        private static (RiskEngine engine, BehaviorAnalyzer az, ManualClock clock, List<Signal> sigs) Make()
        {
            var clock = new ManualClock(T0);
            var e = new RiskEngine(GuardPolicy.Default, clock);
            var sigs = new List<Signal>();
            e.SignalReceived += (_, s) => sigs.Add(s);
            return (e, new BehaviorAnalyzer(e), clock, sigs);
        }

        [Fact]
        public void 机器节律点击_固定间隔_触发RoboticTiming()
        {
            var (_, az, clock, sigs) = Make();
            for (int i = 0; i < 15; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(500));
                az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 100 + i, 100));
                az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 100 + i, 100));
            }
            Assert.Contains(sigs, s => s.Kind == SignalKind.RoboticTiming);
        }

        [Fact]
        public void 人类节律点击_随机间隔_不触发()
        {
            var (_, az, clock, sigs) = Make();
            var rng = new Random(42);
            for (int i = 0; i < 30; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(300 + rng.Next(900)));
                az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 100 + i * 7, 120 + i * 3));
                az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 100 + i * 7, 120 + i * 3));
            }
            Assert.DoesNotContain(sigs, s => s.Kind == SignalKind.RoboticTiming);
            Assert.DoesNotContain(sigs, s => s.Kind == SignalKind.SuperhumanRate);
        }

        [Fact]
        public void 鼠标瞬移点击_触发TeleportClick()
        {
            var (_, az, clock, sigs) = Make();
            az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 10, 10));
            clock.Advance(TimeSpan.FromMilliseconds(800));
            az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 900, 600));
            Assert.Contains(sigs, s => s.Kind == SignalKind.TeleportClick);
        }

        [Fact]
        public void 正常移动后点击_不触发Teleport()
        {
            var (_, az, clock, sigs) = Make();
            az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 10, 10));
            for (int i = 1; i <= 20; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(15));
                az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 10 + i * 40, 10 + i * 30));
            }
            clock.Advance(TimeSpan.FromMilliseconds(50));
            az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 810, 610));
            Assert.DoesNotContain(sigs, s => s.Kind == SignalKind.TeleportClick);
        }

        [Fact]
        public void 注入输入直接上报InjectedInput()
        {
            var (_, az, clock, sigs) = Make();
            az.Feed(new InputEvent(InputEventType.KeyDown, clock.Now, injected: true));
            Assert.Single(sigs, s => s.Kind == SignalKind.InjectedInput);
        }

        [Fact]
        public void 超人速率按键_触发SuperhumanRate()
        {
            var (_, az, clock, sigs) = Make();
            for (int i = 0; i < 60; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(30));   // 33 keys/s
                az.Feed(new InputEvent(InputEventType.KeyDown, clock.Now));
            }
            Assert.Contains(sigs, s => s.Kind == SignalKind.SuperhumanRate);
        }

        [Fact]
        public void 固定节拍翻页_触发RhythmicPaging()
        {
            var (_, az, clock, sigs) = Make();
            for (int i = 0; i < 8; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(1200));
                az.Feed(new InputEvent(InputEventType.PageTurn, clock.Now));
            }
            Assert.Contains(sigs, s => s.Kind == SignalKind.RhythmicPaging);
        }

        [Fact]
        public void 剪贴板突发_触发ClipboardBurst()
        {
            var (_, az, clock, sigs) = Make();
            for (int i = 0; i < 10; i++)
            {
                clock.Advance(TimeSpan.FromSeconds(3));
                az.Feed(new InputEvent(InputEventType.ClipboardCopy, clock.Now));
            }
            Assert.Contains(sigs, s => s.Kind == SignalKind.ClipboardBurst);
        }

        [Fact]
        public void 同像素重复点击_触发RepeatedExactClick()
        {
            var (_, az, clock, sigs) = Make();
            var rng = new Random(1);
            for (int i = 0; i < 8; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(400 + rng.Next(800)));
                az.Feed(new InputEvent(InputEventType.MouseMove, clock.Now, 500, 300));
                az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 500, 300));
            }
            Assert.Contains(sigs, s => s.Kind == SignalKind.RepeatedExactClick);
        }

        [Fact]
        public void 冷却时间内同类信号只报一次()
        {
            var (_, az, clock, sigs) = Make();
            for (int i = 0; i < 40; i++)
            {
                clock.Advance(TimeSpan.FromMilliseconds(500));
                az.Feed(new InputEvent(InputEventType.MouseClick, clock.Now, 100, 100 + i));
            }
            // 20s 内 40 次点击,节律信号受 15s 冷却限制
            Assert.InRange(sigs.Count(s => s.Kind == SignalKind.RoboticTiming), 1, 2);
        }

        [Fact]
        public void 变异系数计算()
        {
            Assert.Equal(0, BehaviorAnalyzer.CoefficientOfVariation(new double[] { 500, 500, 500, 500 }), 6);
            Assert.True(BehaviorAnalyzer.CoefficientOfVariation(new double[] { 100, 900, 300, 700 }) > 0.5);
        }
    }
}
