using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace SteelGuard.AntiRpa.Core.Risk
{
    /// <summary>单个信号的评分参数。</summary>
    public sealed class SignalWeight
    {
        [JsonPropertyName("weight")] public double Weight { get; set; }
        [JsonPropertyName("half_life_sec")] public double HalfLifeSeconds { get; set; } = 600;
        /// <summary>同类信号累计上限(防止单一信号刷满)。</summary>
        [JsonPropertyName("cap")] public double Cap { get; set; } = 100;

        public SignalWeight() { }
        public SignalWeight(double weight, double halfLifeSeconds, double cap = 100)
        {
            Weight = weight; HalfLifeSeconds = halfLifeSeconds; Cap = cap;
        }
    }

    /// <summary>导出配额。</summary>
    public sealed class ExportQuota
    {
        [JsonPropertyName("max_rows_per_export")] public int MaxRowsPerExport { get; set; } = 20000;
        [JsonPropertyName("max_exports_per_hour")] public int MaxExportsPerHour { get; set; } = 10;
        [JsonPropertyName("max_rows_per_day")] public long MaxRowsPerDay { get; set; } = 200000;
        /// <summary>超过该行数需服务端审批 token。</summary>
        [JsonPropertyName("approval_threshold_rows")] public int ApprovalThresholdRows { get; set; } = 5000;
        /// <summary>导出前强制随机延迟范围(毫秒),用于打乱脚本节拍。</summary>
        [JsonPropertyName("delay_min_ms")] public int DelayMinMs { get; set; } = 0;
        [JsonPropertyName("delay_max_ms")] public int DelayMaxMs { get; set; } = 0;
        /// <summary>允许导出的时间窗(小时,本地时间),空 = 不限制。</summary>
        [JsonPropertyName("allowed_hours")] public int[] AllowedHours { get; set; } = Array.Empty<int>();
    }

    /// <summary>
    /// 客户端防护策略。可由服务端 JSON 下发覆盖(<see cref="FromJson"/>),
    /// 默认值来自 <see cref="Default"/>。
    /// </summary>
    public sealed class GuardPolicy
    {
        [JsonPropertyName("version")] public int Version { get; set; } = 1;

        [JsonPropertyName("thresholds")]
        public Dictionary<string, double> Thresholds { get; set; } = new Dictionary<string, double>
        {
            ["elevated"] = 30, ["high"] = 60, ["critical"] = 85,
        };

        [JsonPropertyName("weights")]
        public Dictionary<SignalKind, SignalWeight> Weights { get; set; } = new Dictionary<SignalKind, SignalWeight>();

        [JsonPropertyName("automation_processes")]
        public List<string> AutomationProcesses { get; set; } = new List<string>();

        [JsonPropertyName("remote_control_processes")]
        public List<string> RemoteControlProcesses { get; set; } = new List<string>();

        /// <summary>读屏软件等合法无障碍工具,出现时 UIA 类信号权重降为 0。</summary>
        [JsonPropertyName("accessibility_whitelist")]
        public List<string> AccessibilityWhitelist { get; set; } = new List<string> { "nvda", "jfw", "narrator", "zdsr", "zhengdu" };

        [JsonPropertyName("sensitive_columns")]
        public List<string> SensitiveColumns { get; set; } = new List<string>
        {
            "customer_name", "customer_phone", "contact_phone", "unit_price", "gross_profit",
            "supplier_name", "cost_price", "commission", "credit_limit", "bank_account",
        };

        [JsonPropertyName("export_quota")] public ExportQuota ExportQuota { get; set; } = new ExportQuota();

        /// <summary>WM_GETOBJECT 每分钟阈值(超过即视为 UIA 探测)。</summary>
        [JsonPropertyName("uia_probe_per_minute")] public int UiaProbePerMinute { get; set; } = 40;

        /// <summary>60s 内复制次数阈值。</summary>
        [JsonPropertyName("clipboard_burst_count")] public int ClipboardBurstCount { get; set; } = 10;

        /// <summary>远程会话中注入输入权重乘数(RDP 所有输入都带 INJECTED 标志)。</summary>
        [JsonPropertyName("remote_session_injected_multiplier")] public double RemoteSessionInjectedMultiplier { get; set; } = 0.2;

        /// <summary>启用防截屏窗口属性。</summary>
        [JsonPropertyName("exclude_from_capture")] public bool ExcludeFromCapture { get; set; } = true;

        /// <summary>
        /// RDP / 远程会话中也启用防截屏属性。默认 false:远程桌面的画面本身就是"屏幕捕获",
        /// 开启后合法用户在 RDP 客户端里看到的也是黑块。
        /// </summary>
        [JsonPropertyName("exclude_from_capture_in_remote_session")] public bool ExcludeFromCaptureInRemoteSession { get; set; } = false;

        /// <summary>RDP / 远程会话中强制显示可见屏幕水印(无法阻止客户端侧截屏,只能保证截出来的图可追溯)。</summary>
        [JsonPropertyName("remote_session_force_visible_watermark")] public bool RemoteSessionForceVisibleWatermark { get; set; } = true;

        /// <summary>无障碍模式:关闭 UIA 树隐藏(供视障员工使用)。</summary>
        [JsonPropertyName("accessibility_mode")] public bool AccessibilityMode { get; set; } = false;

        public double ElevatedThreshold => Get("elevated", 30);
        public double HighThreshold => Get("high", 60);
        public double CriticalThreshold => Get("critical", 85);

        private double Get(string k, double d) => Thresholds != null && Thresholds.TryGetValue(k, out var v) ? v : d;

        public SignalWeight WeightOf(SignalKind kind)
        {
            if (Weights != null && Weights.TryGetValue(kind, out var w)) return w;
            return Default.Weights[kind];
        }

        public RiskLevel LevelOf(double score)
        {
            if (score >= CriticalThreshold) return RiskLevel.Critical;
            if (score >= HighThreshold) return RiskLevel.High;
            if (score >= ElevatedThreshold) return RiskLevel.Elevated;
            return RiskLevel.Low;
        }

        // ------------------------------------------------------------------
        private static readonly JsonSerializerOptions JsonOpts = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            Converters = { new JsonStringEnumConverter() },
            DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        };

        public static GuardPolicy FromJson(string json)
        {
            var p = JsonSerializer.Deserialize<GuardPolicy>(json, JsonOpts) ?? new GuardPolicy();
            // 服务端未给的权重回落到默认
            foreach (var kv in Default.Weights)
                if (!p.Weights.ContainsKey(kv.Key)) p.Weights[kv.Key] = kv.Value;
            if (p.AutomationProcesses.Count == 0) p.AutomationProcesses = new List<string>(Default.AutomationProcesses);
            if (p.RemoteControlProcesses.Count == 0) p.RemoteControlProcesses = new List<string>(Default.RemoteControlProcesses);
            return p;
        }

        public string ToJson() => JsonSerializer.Serialize(this, JsonOpts);

        /// <summary>内置默认策略(服务端不可达时使用)。</summary>
        public static GuardPolicy Default { get; } = BuildDefault();

        private static GuardPolicy BuildDefault()
        {
            var p = new GuardPolicy
            {
                Weights = new Dictionary<SignalKind, SignalWeight>
                {
                    [SignalKind.KnownAutomationProcess] = new SignalWeight(40, 1800, 60),
                    [SignalKind.RemoteControlProcess] = new SignalWeight(10, 1800, 15),
                    [SignalKind.InjectedInput] = new SignalWeight(3, 120, 40),
                    [SignalKind.UiaProbing] = new SignalWeight(25, 600, 50),
                    [SignalKind.UiaCoreLoaded] = new SignalWeight(20, 3600, 20),
                    [SignalKind.RoboticTiming] = new SignalWeight(20, 300, 40),
                    [SignalKind.TeleportClick] = new SignalWeight(4, 180, 30),
                    [SignalKind.RepeatedExactClick] = new SignalWeight(10, 300, 20),
                    [SignalKind.SuperhumanRate] = new SignalWeight(15, 300, 30),
                    [SignalKind.RhythmicPaging] = new SignalWeight(20, 600, 40),
                    [SignalKind.ClipboardBurst] = new SignalWeight(15, 300, 30),
                    [SignalKind.ExportAnomaly] = new SignalWeight(20, 1800, 40),
                    [SignalKind.RemoteSession] = new SignalWeight(10, 7200, 10),
                    [SignalKind.DebuggerAttached] = new SignalWeight(30, 3600, 30),
                    [SignalKind.VirtualMachine] = new SignalWeight(5, 7200, 5),
                    [SignalKind.ServerDirective] = new SignalWeight(100, 600, 100),
                },
                AutomationProcesses = new List<string>
                {
                    // 国际 RPA
                    "uipath", "uirobot", "uipath.executor", "uipath.service.host", "uipath.assistant",
                    "automationanywhere", "aaplayer", "aa.bot", "automate", "blueprism",
                    "pad.console.host", "pad.robot", "pad.designer", "pad.browsernativemessaginghost",
                    "winappdriver", "chromedriver", "msedgedriver", "geckodriver", "selenium",
                    "sikuli", "sikulix", "tagui", "robotframework", "flaui", "flauinspect",
                    "inspect", "uispy", "accevent", "accexplorer", "uiaverify",
                    // 国内 RPA
                    "shadowbot", "yingdao", "yingdaorpa", "shadowbot.client", "shadowbot.runner",   // 影刀
                    "uibot", "uibotworker", "uibot creator", "laiye",                              // 来也
                    "isearch", "isrpa", "isearchrpa",                                             // 艺赛旗
                    "encoo", "encoo.robot", "encoo.studio", "yunkuo",                             // 云扩
                    "cyclone", "hongji",                                                          // 弘玑
                    "octopus", "bazhuayu",                                                        // 八爪鱼
                    "qmacro", "anjian", "keymouse", "mouserecorder", "tinytask", "macrorecorder",  // 按键精灵 / 录制回放
                    "autohotkey", "autohotkeyu64", "autohotkeyu32", "autohotkey64", "autoit3", "autoit3_x64",
                    "pywinauto", "pyautogui", "xdotool",
                    // AI 电脑操控 Agent("龙虾" 系:OpenClaw / 腾讯 WorkBuddy 及其 Computer-Use 桥)
                    "openclaw", "clawdbot", "moltbot", "claw", "computer-use", "computeruse",
                    "workbuddy", "tencent workbuddy", "codebuddy", "codebuddy-cli",
                    "windows-bridge", "pi-computer-use", "pi-coding-agent",
                    "anthropic-computer-use", "openinterpreter", "open-interpreter",
                    "ui-tars", "uitars", "agent-s", "browser-use", "playwright", "puppeteer",
                },
                RemoteControlProcesses = new List<string>
                {
                    "teamviewer", "teamviewer_service", "tv_w32", "tv_x64",
                    "anydesk", "todesk", "todesk_service", "sunloginclient", "sunloginremote", "oray",
                    "rustdesk", "splashtop", "vncviewer", "winvnc", "tvnserver", "ultravnc",
                    "mstsc", "rdpclip", "logmein", "ammyy", "radmin", "parsec",
                },
            };
            return p;
        }
    }
}
