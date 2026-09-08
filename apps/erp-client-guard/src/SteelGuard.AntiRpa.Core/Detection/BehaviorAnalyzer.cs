using System;
using System.Collections.Generic;
using System.Linq;
using SteelGuard.AntiRpa.Core.Risk;

namespace SteelGuard.AntiRpa.Core.Detection
{
    public enum InputEventType { MouseMove, MouseClick, KeyDown, PageTurn, ClipboardCopy }

    public readonly struct InputEvent
    {
        public InputEventType Type { get; }
        public DateTimeOffset At { get; }
        public int X { get; }
        public int Y { get; }
        public bool Injected { get; }

        public InputEvent(InputEventType type, DateTimeOffset at, int x = 0, int y = 0, bool injected = false)
        {
            Type = type; At = at; X = x; Y = y; Injected = injected;
        }
    }

    /// <summary>行为分析参数(可由服务端策略覆盖)。</summary>
    public sealed class BehaviorThresholds
    {
        /// <summary>节律判定最少样本数。</summary>
        public int MinSamples { get; set; } = 12;
        /// <summary>变异系数低于此值视为机器节律。</summary>
        public double RoboticCv { get; set; } = 0.08;
        /// <summary>瞬移判定像素距离。</summary>
        public int TeleportPixels { get; set; } = 200;
        /// <summary>瞬移判定:点击前多少毫秒内无移动。</summary>
        public int TeleportQuietMs { get; set; } = 300;
        /// <summary>同一像素点击次数阈值。</summary>
        public int RepeatedClickCount { get; set; } = 8;
        /// <summary>每秒按键上限。</summary>
        public double MaxKeysPerSecond { get; set; } = 15;
        /// <summary>每秒操作(点击 + 按键)上限。</summary>
        public double MaxActionsPerSecond { get; set; } = 6;
        /// <summary>速率判定窗口毫秒。</summary>
        public int RateWindowMs { get; set; } = 2000;
        /// <summary>翻页节律判定最少页数。</summary>
        public int PagingMinCount { get; set; } = 6;
        public double PagingCv { get; set; } = 0.10;
        /// <summary>剪贴板突发:窗口 / 次数。</summary>
        public int ClipboardWindowMs { get; set; } = 60000;
        public int ClipboardBurstCount { get; set; } = 10;
        /// <summary>各类信号最短复报间隔(避免刷屏)。</summary>
        public int CooldownMs { get; set; } = 15000;
    }

    /// <summary>
    /// 纯逻辑的行为分析器:输入事件流 → 行为类信号。
    /// 由 Windows 层的钩子 / 控件事件喂数据;不依赖任何 UI 框架,可单测。
    /// </summary>
    public sealed class BehaviorAnalyzer
    {
        private readonly RiskEngine _engine;
        private readonly BehaviorThresholds _t;
        private readonly object _lock = new object();

        private readonly Queue<InputEvent> _recent = new Queue<InputEvent>();        // 最近 400 条全部事件
        private readonly Queue<DateTimeOffset> _clickTimes = new Queue<DateTimeOffset>();
        private readonly Queue<DateTimeOffset> _keyTimes = new Queue<DateTimeOffset>();
        private readonly Queue<DateTimeOffset> _pageTimes = new Queue<DateTimeOffset>();
        private readonly Queue<DateTimeOffset> _clipTimes = new Queue<DateTimeOffset>();
        private readonly Dictionary<long, int> _clickPixelCounts = new Dictionary<long, int>();
        private readonly Dictionary<SignalKind, DateTimeOffset> _lastFired = new Dictionary<SignalKind, DateTimeOffset>();

        private InputEvent? _lastMove;
        private const int MaxRecent = 400;

        public BehaviorAnalyzer(RiskEngine engine, BehaviorThresholds? thresholds = null)
        {
            _engine = engine ?? throw new ArgumentNullException(nameof(engine));
            _t = thresholds ?? new BehaviorThresholds();
        }

        public BehaviorThresholds Thresholds => _t;

        public void Feed(InputEvent e)
        {
            lock (_lock)
            {
                _recent.Enqueue(e);
                while (_recent.Count > MaxRecent) _recent.Dequeue();

                if (e.Injected && e.Type != InputEventType.MouseMove)
                    _engine.Report(SignalKind.InjectedInput, $"{e.Type} injected");

                switch (e.Type)
                {
                    case InputEventType.MouseMove:
                        _lastMove = e;
                        break;
                    case InputEventType.MouseClick:
                        OnClick(e);
                        break;
                    case InputEventType.KeyDown:
                        OnKey(e);
                        break;
                    case InputEventType.PageTurn:
                        OnPage(e);
                        break;
                    case InputEventType.ClipboardCopy:
                        OnClipboard(e);
                        break;
                }
            }
        }

        // ------------------------------------------------------------------
        private void OnClick(InputEvent e)
        {
            // 瞬移点击:点击前一段时间无移动事件,且与上次已知位置距离很大
            if (_lastMove.HasValue)
            {
                var lm = _lastMove.Value;
                var quiet = (e.At - lm.At).TotalMilliseconds;
                var dist = Math.Sqrt(Math.Pow(e.X - lm.X, 2) + Math.Pow(e.Y - lm.Y, 2));
                if (quiet >= _t.TeleportQuietMs && dist >= _t.TeleportPixels)
                    _engine.Report(SignalKind.TeleportClick, $"jump {dist:0}px after {quiet:0}ms quiet");
            }
            _lastMove = new InputEvent(InputEventType.MouseMove, e.At, e.X, e.Y);

            // 同像素反复点击
            var key = ((long)e.X << 32) | (uint)e.Y;
            _clickPixelCounts[key] = _clickPixelCounts.TryGetValue(key, out var c) ? c + 1 : 1;
            if (_clickPixelCounts.Count > 200) _clickPixelCounts.Clear();
            if (_clickPixelCounts[key] == _t.RepeatedClickCount)
                Fire(SignalKind.RepeatedExactClick, e.At, $"({e.X},{e.Y}) x{_t.RepeatedClickCount}");

            _clickTimes.Enqueue(e.At);
            Trim(_clickTimes, e.At, TimeSpan.FromSeconds(60));
            CheckRhythm(_clickTimes, e.At, SignalKind.RoboticTiming, _t.RoboticCv, _t.MinSamples, "clicks");
            CheckRate(e.At);
        }

        private void OnKey(InputEvent e)
        {
            _keyTimes.Enqueue(e.At);
            Trim(_keyTimes, e.At, TimeSpan.FromSeconds(60));
            var inWin = CountWithin(_keyTimes, e.At, _t.RateWindowMs);
            if (inWin / (_t.RateWindowMs / 1000.0) > _t.MaxKeysPerSecond)
                Fire(SignalKind.SuperhumanRate, e.At, $"{inWin} keys / {_t.RateWindowMs}ms");
            CheckRhythm(_keyTimes, e.At, SignalKind.RoboticTiming, _t.RoboticCv, _t.MinSamples * 2, "keys");
            CheckRate(e.At);
        }

        private void OnPage(InputEvent e)
        {
            _pageTimes.Enqueue(e.At);
            Trim(_pageTimes, e.At, TimeSpan.FromMinutes(5));
            CheckRhythm(_pageTimes, e.At, SignalKind.RhythmicPaging, _t.PagingCv, _t.PagingMinCount, "pages");
        }

        private void OnClipboard(InputEvent e)
        {
            _clipTimes.Enqueue(e.At);
            Trim(_clipTimes, e.At, TimeSpan.FromMilliseconds(_t.ClipboardWindowMs));
            if (_clipTimes.Count >= _t.ClipboardBurstCount)
                Fire(SignalKind.ClipboardBurst, e.At, $"{_clipTimes.Count} copies / {_t.ClipboardWindowMs}ms");
        }

        private void CheckRate(DateTimeOffset now)
        {
            var actions = CountWithin(_clickTimes, now, _t.RateWindowMs) + CountWithin(_keyTimes, now, _t.RateWindowMs);
            if (actions / (_t.RateWindowMs / 1000.0) > _t.MaxActionsPerSecond)
                Fire(SignalKind.SuperhumanRate, now, $"{actions} actions / {_t.RateWindowMs}ms");
        }

        private void CheckRhythm(Queue<DateTimeOffset> times, DateTimeOffset now, SignalKind kind, double cvLimit, int minSamples, string what)
        {
            if (times.Count < minSamples) return;
            var arr = times.ToArray();
            var intervals = new double[arr.Length - 1];
            for (int i = 1; i < arr.Length; i++) intervals[i - 1] = (arr[i] - arr[i - 1]).TotalMilliseconds;
            // 只看最近 N 个间隔,并忽略 < 20ms 的按键重复
            var tail = intervals.Skip(Math.Max(0, intervals.Length - (minSamples - 1))).Where(v => v >= 20).ToArray();
            if (tail.Length < minSamples - 1) return;
            var cv = CoefficientOfVariation(tail);
            if (cv < cvLimit)
                Fire(kind, now, $"{what} cv={cv:0.000} mean={tail.Average():0}ms n={tail.Length}");
        }

        /// <summary>变异系数 = 标准差 / 均值。</summary>
        public static double CoefficientOfVariation(IReadOnlyCollection<double> values)
        {
            if (values.Count < 2) return double.PositiveInfinity;
            var mean = values.Average();
            if (mean <= 0) return double.PositiveInfinity;
            var var = values.Sum(v => (v - mean) * (v - mean)) / (values.Count - 1);
            return Math.Sqrt(var) / mean;
        }

        private static void Trim(Queue<DateTimeOffset> q, DateTimeOffset now, TimeSpan window)
        {
            while (q.Count > 0 && now - q.Peek() > window) q.Dequeue();
        }

        private static int CountWithin(Queue<DateTimeOffset> q, DateTimeOffset now, int ms)
        {
            var cutoff = now.AddMilliseconds(-ms);
            return q.Count(t => t >= cutoff);
        }

        private void Fire(SignalKind kind, DateTimeOffset now, string detail)
        {
            if (_lastFired.TryGetValue(kind, out var last) && (now - last).TotalMilliseconds < _t.CooldownMs) return;
            _lastFired[kind] = now;
            _engine.Report(kind, detail);
        }
    }
}
