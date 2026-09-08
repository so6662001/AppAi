using System;
using System.Collections.Generic;
using System.Linq;

namespace SteelGuard.AntiRpa.Core.Risk
{
    public sealed class RiskLevelChangedEventArgs : EventArgs
    {
        public RiskLevel Previous { get; }
        public RiskLevel Current { get; }
        public double Score { get; }
        public Signal Trigger { get; }
        public RiskLevelChangedEventArgs(RiskLevel prev, RiskLevel cur, double score, Signal trigger)
        {
            Previous = prev; Current = cur; Score = score; Trigger = trigger;
        }
    }

    /// <summary>
    /// 风险评分引擎:信号带权重与半衰期,得分随时间指数衰减,同类信号有累计上限。
    /// 线程安全(所有公开方法加锁)。
    /// </summary>
    public sealed class RiskEngine
    {
        private readonly object _lock = new object();
        private readonly List<Signal> _signals = new List<Signal>();
        private readonly IGuardClock _clock;
        private GuardPolicy _policy;
        private RiskLevel _lastLevel = RiskLevel.Low;
        private bool _remoteSession;
        private bool _accessibilityToolPresent;

        /// <summary>保留窗口:比最长半衰期 × 6 更久的信号直接丢弃(贡献 < 2%)。</summary>
        private static readonly TimeSpan MaxRetention = TimeSpan.FromHours(12);

        public event EventHandler<RiskLevelChangedEventArgs>? LevelChanged;
        public event EventHandler<Signal>? SignalReceived;

        public RiskEngine(GuardPolicy? policy = null, IGuardClock? clock = null)
        {
            _policy = policy ?? GuardPolicy.Default;
            _clock = clock ?? SystemClock.Instance;
        }

        public GuardPolicy Policy
        {
            get { lock (_lock) return _policy; }
        }

        public void UpdatePolicy(GuardPolicy policy)
        {
            lock (_lock) _policy = policy ?? throw new ArgumentNullException(nameof(policy));
            Reevaluate();
        }

        /// <summary>标记当前处于远程会话(RDP),注入输入信号自动降权。</summary>
        public bool RemoteSession
        {
            get { lock (_lock) return _remoteSession; }
            set { lock (_lock) _remoteSession = value; }
        }

        /// <summary>检测到合法读屏软件时,UIA 类信号权重归零。</summary>
        public bool AccessibilityToolPresent
        {
            get { lock (_lock) return _accessibilityToolPresent; }
            set { lock (_lock) _accessibilityToolPresent = value; }
        }

        /// <summary>上报一个信号(使用策略默认权重)。</summary>
        public Signal Report(SignalKind kind, string? detail = null) => Report(kind, null, detail);

        /// <summary>上报一个信号,可覆盖权重(例如根据严重程度放大)。</summary>
        public Signal Report(SignalKind kind, double? weightOverride, string? detail = null)
        {
            Signal sig;
            RiskLevel prev, cur; double score;
            lock (_lock)
            {
                var w = weightOverride ?? _policy.WeightOf(kind).Weight;
                w = AdjustWeight(kind, w);
                sig = new Signal(kind, w, _clock.Now, detail);
                _signals.Add(sig);
                Prune();
                prev = _lastLevel;
                score = ScoreUnsafe();
                cur = _policy.LevelOf(score);
                _lastLevel = cur;
            }
            SignalReceived?.Invoke(this, sig);
            if (cur != prev) LevelChanged?.Invoke(this, new RiskLevelChangedEventArgs(prev, cur, score, sig));
            return sig;
        }

        private double AdjustWeight(SignalKind kind, double w)
        {
            if (kind == SignalKind.InjectedInput && _remoteSession) w *= _policy.RemoteSessionInjectedMultiplier;
            if ((kind == SignalKind.UiaProbing || kind == SignalKind.UiaCoreLoaded) &&
                (_accessibilityToolPresent || _policy.AccessibilityMode)) w = 0;
            return w;
        }

        public double Score
        {
            get { lock (_lock) return ScoreUnsafe(); }
        }

        public RiskLevel Level
        {
            get { lock (_lock) return _policy.LevelOf(ScoreUnsafe()); }
        }

        /// <summary>按信号类型分解当前得分(用于解释 / 上报)。</summary>
        public IReadOnlyDictionary<SignalKind, double> Breakdown()
        {
            lock (_lock)
            {
                var now = _clock.Now;
                var d = new Dictionary<SignalKind, double>();
                foreach (var g in _signals.GroupBy(s => s.Kind))
                {
                    var sw = _policy.WeightOf(g.Key);
                    var sum = g.Sum(s => Decay(s, now, sw.HalfLifeSeconds));
                    d[g.Key] = Math.Min(sum, sw.Cap);
                }
                return d;
            }
        }

        public IReadOnlyList<Signal> RecentSignals(int max = 50)
        {
            lock (_lock) return _signals.OrderByDescending(s => s.At).Take(max).ToList();
        }

        /// <summary>手动清零(例如人机挑战通过后)。</summary>
        public void Reset()
        {
            lock (_lock)
            {
                _signals.Clear();
                _lastLevel = RiskLevel.Low;
            }
        }

        /// <summary>时间推进后重新评估等级(定时器调用,以便衰减后触发降级事件)。</summary>
        public void Reevaluate()
        {
            RiskLevel prev, cur; double score;
            lock (_lock)
            {
                Prune();
                prev = _lastLevel;
                score = ScoreUnsafe();
                cur = _policy.LevelOf(score);
                _lastLevel = cur;
            }
            if (cur != prev)
                LevelChanged?.Invoke(this, new RiskLevelChangedEventArgs(prev, cur, score,
                    new Signal(SignalKind.ServerDirective, 0, _clock.Now, "decay")));
        }

        private double ScoreUnsafe()
        {
            var now = _clock.Now;
            double total = 0;
            foreach (var g in _signals.GroupBy(s => s.Kind))
            {
                var sw = _policy.WeightOf(g.Key);
                var sum = 0.0;
                foreach (var s in g) sum += Decay(s, now, sw.HalfLifeSeconds);
                total += Math.Min(sum, sw.Cap);
            }
            return Math.Min(100, total);
        }

        private static double Decay(Signal s, DateTimeOffset now, double halfLifeSec)
        {
            if (halfLifeSec <= 0) return s.Weight;
            var elapsed = (now - s.At).TotalSeconds;
            if (elapsed <= 0) return s.Weight;
            return s.Weight * Math.Pow(0.5, elapsed / halfLifeSec);
        }

        private void Prune()
        {
            var cutoff = _clock.Now - MaxRetention;
            _signals.RemoveAll(s => s.At < cutoff);
            if (_signals.Count > 5000) _signals.RemoveRange(0, _signals.Count - 5000);
        }
    }
}
