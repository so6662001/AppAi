using System;
using System.Collections.Generic;
using System.Linq;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using Xunit;

namespace SteelGuard.Tests
{
    public class PolicyEngineTests
    {
        private static readonly GuardPolicy P = GuardPolicy.Default;

        [Fact]
        public void 低风险导出_允许并带水印和蜜罐()
        {
            var d = PolicyEngine.Decide(P, RiskLevel.Low, 5, GuardOperation.Export, DataSensitivity.Confidential, 1000);
            Assert.True(d.Allowed);
            Assert.True(d.Has(GuardAction.Watermark));
            Assert.True(d.Has(GuardAction.Canary));
            Assert.False(d.RequiresApproval);
            Assert.Equal(20000, d.RowLimit);
        }

        [Fact]
        public void 超过审批阈值_需要审批()
        {
            var d = PolicyEngine.Decide(P, RiskLevel.Low, 5, GuardOperation.Export, DataSensitivity.Internal, 8000);
            Assert.True(d.RequiresApproval);
        }

        [Fact]
        public void Elevated导出_行数减半并延迟()
        {
            var d = PolicyEngine.Decide(P, RiskLevel.Elevated, 45, GuardOperation.Export, DataSensitivity.Internal, 100, new Random(1));
            Assert.True(d.Allowed);
            Assert.Equal(10000, d.RowLimit);
            Assert.True(d.Has(GuardAction.Delay));
            Assert.InRange(d.DelayMs, 2000, 5000);
        }

        [Fact]
        public void High导出_需要挑战和审批_敏感列脱敏()
        {
            var d = PolicyEngine.Decide(P, RiskLevel.High, 70, GuardOperation.Export, DataSensitivity.Confidential, 100);
            Assert.True(d.RequiresChallenge);
            Assert.True(d.RequiresApproval);
            Assert.True(d.Has(GuardAction.Mask));
            Assert.Equal(5000, d.RowLimit);
        }

        [Fact]
        public void Critical一律拒绝并锁定()
        {
            foreach (var op in new[] { GuardOperation.View, GuardOperation.Copy, GuardOperation.Export })
            {
                var d = PolicyEngine.Decide(P, RiskLevel.Critical, 90, op);
                Assert.False(d.Allowed);
                Assert.True(d.Has(GuardAction.LockSession));
            }
        }

        [Fact]
        public void High复制被拒绝_Elevated复制限50行()
        {
            Assert.False(PolicyEngine.Decide(P, RiskLevel.High, 70, GuardOperation.Copy).Allowed);
            var d = PolicyEngine.Decide(P, RiskLevel.Elevated, 40, GuardOperation.Copy);
            Assert.True(d.Allowed);
            Assert.Equal(50, d.RowLimit);
        }

        [Fact]
        public void 无障碍模式下不隐藏UIA树()
        {
            var p = GuardPolicy.FromJson(@"{""accessibility_mode"": true}");
            var d = PolicyEngine.Decide(p, RiskLevel.Elevated, 40, GuardOperation.View);
            Assert.False(d.Has(GuardAction.HideAccessibilityTree));
        }
    }

    public class ExportGovernorTests
    {
        private static readonly DateTimeOffset T0 = new DateTimeOffset(2026, 9, 8, 9, 0, 0, TimeSpan.FromHours(8));
        private const string Secret = "unit-test-secret";

        private static (ExportGovernor gov, RiskEngine eng, ManualClock clock) Make(GuardPolicy? p = null)
        {
            var clock = new ManualClock(T0);
            var eng = new RiskEngine(p ?? GuardPolicy.Default, clock);
            return (new ExportGovernor(eng, clock), eng, clock);
        }

        [Fact]
        public void 每小时次数配额()
        {
            var (gov, _, clock) = Make();
            for (int i = 0; i < 10; i++)
            {
                Assert.True(gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 100 }).Allowed);
                gov.RecordExport(100);
                clock.Advance(TimeSpan.FromMinutes(1));
            }
            var d = gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 100 });
            Assert.False(d.Allowed);
            Assert.Contains("次数", d.Reason);
            clock.Advance(TimeSpan.FromHours(1));
            Assert.True(gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 100 }).Allowed);
        }

        [Fact]
        public void 每日行数配额()
        {
            var p = GuardPolicy.FromJson(@"{""export_quota"": {""max_rows_per_day"": 1000, ""max_exports_per_hour"": 100, ""approval_threshold_rows"": 100000}}");
            var (gov, _, clock) = Make(p);
            gov.RecordExport(900);
            clock.Advance(TimeSpan.FromMinutes(5));
            var d = gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 200 });
            Assert.False(d.Allowed);
            Assert.Contains("今日", d.Reason);
        }

        [Fact]
        public void 超阈值无token_返回需审批且不允许()
        {
            var (gov, _, _) = Make();
            var d = gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 9000 });
            Assert.False(d.Allowed);
            Assert.True(d.RequiresApproval);
            Assert.False(d.Has(GuardAction.Deny));   // 不是拒绝,是待审批
        }

        [Fact]
        public void 有效审批token_放行()
        {
            var (gov, _, clock) = Make();
            var verifier = new ApprovalTokenVerifier(Secret, 1001, 1023);
            var token = ApprovalTokenVerifier.Issue(Secret, 1001, 1023, "so", 10000, clock.Now.AddMinutes(30), "李经理");
            var d = gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 9000, ApprovalToken = token }, verifier);
            Assert.True(d.Allowed);
            Assert.Contains(d.Explanations, x => x.Contains("李经理"));
        }

        [Theory]
        [InlineData("wrong-secret", 1001, 1023, "so", 10000, 30, "signature")]
        [InlineData(Secret, 1002, 1023, "so", 10000, 30, "tenant")]
        [InlineData(Secret, 1001, 9999, "so", 10000, 30, "user")]
        [InlineData(Secret, 1001, 1023, "other", 10000, 30, "dataset")]
        [InlineData(Secret, 1001, 1023, "so", 5000, 30, "rows")]
        [InlineData(Secret, 1001, 1023, "so", 10000, -5, "expired")]
        public void 无效token各种原因(string secret, long t, long u, string ds, int maxRows, int expMin, string err)
        {
            var (gov, eng, clock) = Make();
            var verifier = new ApprovalTokenVerifier(Secret, 1001, 1023);
            var token = ApprovalTokenVerifier.Issue(secret, t, u, ds, maxRows, clock.Now.AddMinutes(expMin), "x");
            var d = gov.Evaluate(new ExportRequest { DataSet = "so", RowCount = 9000, ApprovalToken = token }, verifier);
            Assert.False(d.Allowed);
            Assert.Contains(err, d.Reason);
            Assert.True(eng.Score > 0);   // 伪造 token 本身是一个信号
        }

        [Fact]
        public void 与Python服务端签发的token二进制兼容()
        {
            // 由 services/client-guard-service/tests/test_approval.py::test_known_vector_matches_csharp 生成
            const string token = "MTAwMXwxMDIzfHNhbGVzX29yZGVyfDUwMDB8MTkwMDAwMDAwMHznjovmgLt8ZGVhZGJlZWY.4zgUDwUnEAc4_gdfWoanQX65uO2U4Z_OErfgOTZqP18";
            var verifier = new ApprovalTokenVerifier("cross-lang-secret", 1001, 1023);
            var r = verifier.Verify(token, "sales_order", 4000, DateTimeOffset.FromUnixTimeSeconds(1_899_999_000));
            Assert.True(r.Valid, r.Error);
            Assert.Equal("王总", r.Approver);
            Assert.Equal(5000, r.MaxRows);

            var mine = ApprovalTokenVerifier.Issue("cross-lang-secret", 1001, 1023, "sales_order", 5000,
                DateTimeOffset.FromUnixTimeSeconds(1_900_000_000), "王总", "deadbeef");
            Assert.Equal(token, mine);
        }

        [Fact]
        public void 篡改token_签名失败()
        {
            var verifier = new ApprovalTokenVerifier(Secret, 1, 2);
            var token = ApprovalTokenVerifier.Issue(Secret, 1, 2, "so", 100, T0.AddHours(1), "a");
            var tampered = token.Substring(0, 5) + (token[5] == 'A' ? 'B' : 'A') + token.Substring(6);
            Assert.False(verifier.Verify(tampered, "so", 50, T0).Valid);
            Assert.False(verifier.Verify("garbage", "so", 50, T0).Valid);
            Assert.False(verifier.Verify("", "so", 50, T0).Valid);
        }
    }

    public class WatermarkTests
    {
        [Fact]
        public void 隐形水印可编码解码()
        {
            var enc = Watermark.Encode("1023:abcdef12:7");
            Assert.All(enc, c => Assert.Contains(c, new[] { Watermark.ZeroBit, Watermark.OneBit, Watermark.End, Watermark.Start }));
            var text = "上" + enc + "海鑫源钢铁贸易有限公司";
            var payloads = Watermark.Decode(text);
            Assert.Single(payloads);
            Assert.Equal("1023:abcdef12:7", payloads[0]);
            Assert.True(Watermark.TryParsePayload(payloads[0], out var uid, out var exp, out var seq));
            Assert.Equal(1023, uid);
            Assert.Equal("abcdef12", exp);
            Assert.Equal(7, seq);
        }

        [Fact]
        public void Strip去掉水印后文本原样()
        {
            var ctx = new WatermarkContext { UserId = 5, ExportId = "deadbeef0000" };
            var marked = Watermark.Mark("华达金属", ctx, 0);
            Assert.NotEqual("华达金属", marked);
            Assert.Equal("华达金属", Watermark.Strip(marked));
        }

        [Fact]
        public void Apply按间隔植入且不修改原数据()
        {
            var rows = Enumerable.Range(0, 100).Select(i => new Dictionary<string, object?>
            {
                ["order_no"] = $"SO{i:D4}", ["customer_name"] = "客户" + i, ["amount"] = i * 10.0,
            }).ToList();
            var ctx = new WatermarkContext { UserId = 77, ExportId = "0123456789ab" };
            var outRows = Watermark.Apply(rows, ctx, new[] { "customer_name" }, everyNRows: 25);

            Assert.Equal(100, outRows.Count);
            Assert.Equal("客户0", rows[0]["customer_name"]);                        // 原数据未变
            var decoded = outRows.SelectMany(r => Watermark.Decode((string)r["customer_name"]!)).ToList();
            Assert.Equal(4, decoded.Count);                                             // 0,25,50,75
            Assert.All(decoded, p => Assert.StartsWith("77:01234567:", p));
        }

        [Fact]
        public void 多段水印文本中全部解出()
        {
            var ctx = new WatermarkContext { UserId = 1, ExportId = "aaaaaaaaaaaa" };
            var s = Watermark.Mark("甲公司", ctx, 0) + "\t" + Watermark.Mark("乙公司", ctx, 1);
            Assert.Equal(2, Watermark.Decode(s).Count);
        }
    }

    public class CanaryTests
    {
        private static CanaryData.Context Ctx(long user = 1023) => new CanaryData.Context
        {
            TenantId = 1001, UserId = user, Secret = "canary-secret", Count = 2,
            Day = new DateTimeOffset(2026, 9, 8, 10, 0, 0, TimeSpan.FromHours(8)),
        };

        private static readonly string[] Cols = { "order_no", "customer_name", "contact_phone", "material_grade", "tonnage", "unit_price", "amount" };

        [Fact]
        public void 确定性_同上下文生成相同蜜罐()
        {
            var a = CanaryData.Generate(Ctx(), Cols);
            var b = CanaryData.Generate(Ctx(), Cols);
            Assert.Equal(a.Count, b.Count);
            for (int i = 0; i < a.Count; i++)
                foreach (var c in Cols) Assert.Equal(a[i][c]?.ToString(), b[i][c]?.ToString());
        }

        [Fact]
        public void 不同用户蜜罐不同_可溯源()
        {
            var a = CanaryData.Generate(Ctx(1023), Cols);
            var b = CanaryData.Generate(Ctx(2048), Cols);
            Assert.NotEqual(a[0]["customer_name"], b[0]["customer_name"]);

            var leaked = new Dictionary<string, object?>(a[0]);
            leaked.Remove("__canary");
            Assert.True(CanaryData.Matches(leaked, Ctx(1023), new[] { "customer_name", "order_no" }));
            Assert.False(CanaryData.Matches(leaked, Ctx(2048), new[] { "customer_name", "order_no" }));
        }

        [Fact]
        public void 蜜罐字段看起来真实()
        {
            var row = CanaryData.Generate(Ctx(), Cols)[0];
            Assert.EndsWith("有限公司", row["customer_name"]!.ToString());
            Assert.Matches(@"^1[3-8]\d{9}$", row["contact_phone"]!.ToString());
            Assert.StartsWith("SO260908", row["order_no"]!.ToString());
            Assert.InRange(Convert.ToDouble(row["unit_price"]), 3300, 4800);
        }

        [Fact]
        public void Inject插入到中间并移除内部标记()
        {
            var rows = Enumerable.Range(0, 50).Select(i => Cols.ToDictionary(c => c, c => (object?)$"{c}-{i}")).ToList();
            var outRows = CanaryData.Inject(rows, Ctx());
            Assert.Equal(52, outRows.Count);
            Assert.All(outRows, r => Assert.False(r.ContainsKey("__canary")));
            Assert.Equal("order_no-0", outRows[0]["order_no"]);   // 首行保持真实,蜜罐插在中间
            Assert.Equal(2, outRows.Count(r => !r["order_no"]!.ToString()!.StartsWith("order_no-")));
        }
    }

    public class DataMaskerTests
    {
        [Theory]
        [InlineData("contact_phone", "13812345678", "138****5678")]
        [InlineData("customer_name", "上海鑫源钢铁贸易有限公司", "上******")]
        [InlineData("unit_price", "3850", "3***")]
        [InlineData("gross_profit", "-12345.6", "-1****")]
        [InlineData("bank_account", "6222021234567890", "**** 7890")]
        public void 按列名脱敏(string col, string val, string expected) => Assert.Equal(expected, DataMasker.Mask(col, val));

        [Fact]
        public void MaskRows只改敏感列且不改原数据()
        {
            var rows = new List<Dictionary<string, object?>>
            {
                new Dictionary<string, object?> { ["order_no"] = "SO1", ["customer_name"] = "甲乙丙公司", ["unit_price"] = 4000 },
            };
            var m = DataMasker.MaskRows(rows, new[] { "customer_name", "unit_price" });
            Assert.Equal("SO1", m[0]["order_no"]);
            Assert.Equal("甲****", m[0]["customer_name"]);
            Assert.Equal("4***", m[0]["unit_price"]);
            Assert.Equal("甲乙丙公司", rows[0]["customer_name"]);
        }
    }

    public class ProcessMatcherTests
    {
        private static readonly ProcessMatcher M = new ProcessMatcher(GuardPolicy.Default);

        [Theory]
        [InlineData("UiRobot.exe", ProcessCategory.Automation)]
        [InlineData("UiPath.Executor", ProcessCategory.Automation)]
        [InlineData("ShadowBot.Client", ProcessCategory.Automation)]
        [InlineData("AutoHotkey64", ProcessCategory.Automation)]
        [InlineData("PAD.Console.Host", ProcessCategory.Automation)]
        [InlineData("openclaw", ProcessCategory.Automation)]
        [InlineData("ToDesk", ProcessCategory.RemoteControl)]
        [InlineData("SunloginClient", ProcessCategory.RemoteControl)]
        [InlineData("nvda", ProcessCategory.Accessibility)]
        [InlineData("explorer", ProcessCategory.None)]
        [InlineData("chrome", ProcessCategory.None)]
        [InlineData("clawdeck", ProcessCategory.None)]          // "claw" 需要非字母边界
        [InlineData("automatedbackup", ProcessCategory.None)]  // "automate" 不做子串匹配
        public void 分类(string name, ProcessCategory expected) => Assert.Equal(expected, M.Classify(name));

        [Fact]
        public void Scan去重并只返回命中()
        {
            var hits = M.Scan(new[] { "explorer", "UiRobot", "uirobot", "ToDesk", "svchost" });
            Assert.Equal(2, hits.Count);
        }
    }
}
