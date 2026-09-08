using System.Linq;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using Xunit;

namespace SteelGuard.Tests
{
    /// <summary>模拟 MsRdpClient9 控件的对象模型(后期绑定路径与真实 COM 对象一致)。</summary>
    public class FakeAdvancedSettings
    {
        public bool RedirectClipboard { get; set; } = true;
        public bool RedirectDrives { get; set; } = true;
        public bool RedirectPrinters { get; set; } = true;
        public bool RedirectSmartCards { get; set; }
        public bool RedirectPorts { get; set; } = true;
        public bool RedirectDevices { get; set; } = true;
        public bool RedirectPOSDevices { get; set; } = true;
        public bool EnableCredSspSupport { get; set; }
        public uint AuthenticationLevel { get; set; }
        public bool DisplayConnectionBar { get; set; } = true;
    }

    public class FakeSecuredSettings
    {
        public string StartProgram { get; set; } = "";
        public string WorkDir { get; set; } = "";
    }

    public class FakeRdpOcx
    {
        public FakeAdvancedSettings AdvancedSettings9 { get; } = new FakeAdvancedSettings();
        public FakeSecuredSettings SecuredSettings2 { get; } = new FakeSecuredSettings();
        public int Connected { get; set; } = 1;
        public int DisconnectCalls;
        public void Disconnect() { DisconnectCalls++; Connected = 0; }
    }

    /// <summary>老版本控件:只有 AdvancedSettings2,没有 RedirectDevices / CredSSP。</summary>
    public class FakeOldOcx
    {
        public class Adv2 { public bool RedirectClipboard { get; set; } = true; public bool RedirectDrives { get; set; } = true; public bool RedirectPrinters { get; set; } = true; }
        public Adv2 AdvancedSettings2 { get; } = new Adv2();
        public int Connected { get; set; }
    }

    public class FakeAxHost
    {
        public FakeRdpOcx Inner { get; } = new FakeRdpOcx();
        public object GetOcx() => Inner;
    }

    public class RdpLauncherTests
    {
        [Fact]
        public void Hardening_TurnsOffLeakChannels_AndSetsStartProgram()
        {
            var ocx = new FakeRdpOcx();
            var rep = RdpControlHardening.Apply(ocx, new RdpHardening(), allowClipboard: false,
                startProgram: @"C:\SteelERP\SteelErp.exe --guard-ticket=abc", workDir: @"C:\SteelERP");

            Assert.False(ocx.AdvancedSettings9.RedirectClipboard);
            Assert.False(ocx.AdvancedSettings9.RedirectDrives);
            Assert.False(ocx.AdvancedSettings9.RedirectPorts);
            Assert.False(ocx.AdvancedSettings9.RedirectDevices);
            Assert.False(ocx.AdvancedSettings9.RedirectPOSDevices);
            Assert.True(ocx.AdvancedSettings9.RedirectPrinters);
            Assert.True(ocx.AdvancedSettings9.EnableCredSspSupport);
            Assert.Equal(2u, ocx.AdvancedSettings9.AuthenticationLevel);
            Assert.Equal(@"C:\SteelERP\SteelErp.exe --guard-ticket=abc", ocx.SecuredSettings2.StartProgram);
            Assert.Equal(@"C:\SteelERP", ocx.SecuredSettings2.WorkDir);
            Assert.False(rep.ClipboardRedirected);
            Assert.False(rep.DrivesRedirected);
            Assert.Contains(rep.Applied, s => s.StartsWith("AdvancedSettings9.RedirectClipboard"));
            Assert.True(RdpControlHardening.VerifyLockedDown(ocx, new RdpHardening(), allowClipboard: false));
        }

        [Fact]
        public void Hardening_ClipboardFollowsRiskAndPolicy()
        {
            var ocx = new FakeRdpOcx();
            var p = new RdpHardening { RedirectClipboard = false, RedirectClipboardWhenLowRisk = true };
            RdpControlHardening.Apply(ocx, p, allowClipboard: true);
            Assert.True(ocx.AdvancedSettings9.RedirectClipboard);

            p.RedirectClipboardWhenLowRisk = false;
            RdpControlHardening.Apply(ocx, p, allowClipboard: true);
            Assert.False(ocx.AdvancedSettings9.RedirectClipboard);

            // 宿主事后偷偷打开 → 复核失败
            ocx.AdvancedSettings9.RedirectDrives = true;
            Assert.False(RdpControlHardening.VerifyLockedDown(ocx, p, allowClipboard: false));
        }

        [Fact]
        public void Hardening_FallsBackToOlderAdvancedSettings()
        {
            var ocx = new FakeOldOcx();
            var rep = RdpControlHardening.Apply(ocx, new RdpHardening(), allowClipboard: false, startProgram: "erp.exe");
            Assert.False(ocx.AdvancedSettings2.RedirectClipboard);
            Assert.False(ocx.AdvancedSettings2.RedirectDrives);
            Assert.Contains(rep.Applied, s => s.StartsWith("AdvancedSettings2.RedirectClipboard"));
            Assert.Contains(rep.Failed, s => s.StartsWith("AdvancedSettings2.EnableCredSspSupport"));
            Assert.Contains(rep.Failed, s => s.StartsWith("SecuredSettings*"));
        }

        [Fact]
        public void Hardening_UnwrapsAxHost_AndDisconnects()
        {
            var ax = new FakeAxHost();
            RdpControlHardening.Apply(ax, new RdpHardening(), false);
            Assert.False(ax.Inner.AdvancedSettings9.RedirectClipboard);
            Assert.Equal(1, RdpControlHardening.ConnectionState(ax));
            Assert.True(RdpControlHardening.Disconnect(ax));
            Assert.Equal(1, ax.Inner.DisconnectCalls);
            Assert.Equal(0, RdpControlHardening.ConnectionState(ax));
            Assert.True(RdpControlHardening.Disconnect(ax));    // 已断开不再调用
            Assert.Equal(1, ax.Inner.DisconnectCalls);
        }

        [Fact]
        public void Hardening_NotAnRdpControl_ReportsFailure()
        {
            var rep = RdpControlHardening.Apply(new object(), new RdpHardening(), false);
            Assert.Contains(rep.Failed, s => s.StartsWith("AdvancedSettings*"));
            Assert.Empty(rep.Applied);
            Assert.Equal(-1, RdpControlHardening.ConnectionState(new object()));
        }

        [Fact]
        public void GuardTicket_BuildAndParse()
        {
            var cmd = GuardTicket.BuildCommandLine(@"C:\Steel ERP\SteelErp.exe", "tkt.sig", "--tenant=1001");
            Assert.Equal("\"C:\\Steel ERP\\SteelErp.exe\" --guard-ticket=tkt.sig --tenant=1001", cmd);

            Assert.Equal("tkt.sig", GuardTicket.FromArgs(new[] { @"C:\Steel ERP\SteelErp.exe", "--guard-ticket=tkt.sig", "--tenant=1001" }));
            Assert.Equal("tkt.sig", GuardTicket.FromArgs(new[] { "erp.exe", "--guard-ticket", "\"tkt.sig\"" }));
            Assert.Null(GuardTicket.FromArgs(new[] { "erp.exe", "--tenant=1" }));
            Assert.Null(GuardTicket.FromArgs(new[] { "erp.exe", "--guard-ticket=" }));
            Assert.Null(GuardTicket.FromArgs(null));
        }

        [Fact]
        public void Policy_RdpSection_RoundTripsJson_WithDefaults()
        {
            var json = GuardPolicy.Default.ToJson();
            Assert.Contains("\"rdp\"", json);
            var p = GuardPolicy.FromJson(json);
            Assert.False(p.Rdp.RedirectClipboard);
            Assert.False(p.Rdp.RedirectDrives);
            Assert.True(p.Rdp.StartProgramOnly);
            Assert.True(p.Rdp.LauncherExcludeFromCapture);
            Assert.Equal(RiskLevel.Critical, p.Rdp.DisconnectAtLevel);

            // 服务端下发未知字段(仅服务端使用的 unpaired_remote_export 等)应被忽略
            var fromServer = GuardPolicy.FromJson("{\"version\":3,\"rdp\":{\"redirect_clipboard\":true,\"unpaired_remote_export\":\"deny\",\"disconnect_at_level\":2}}");
            Assert.True(fromServer.Rdp.RedirectClipboard);
            Assert.Equal(RiskLevel.High, fromServer.Rdp.DisconnectAtLevel);
            Assert.Equal(GuardPolicy.Default.Weights[SignalKind.UnpairedRemoteSession].Weight, fromServer.WeightOf(SignalKind.UnpairedRemoteSession).Weight);
        }

        [Fact]
        public void UnpairedRemoteSession_HasDefaultWeight()
        {
            var w = GuardPolicy.Default.WeightOf(SignalKind.UnpairedRemoteSession);
            Assert.Equal(25, w.Weight);
            var e = new RiskEngine(GuardPolicy.Default, new ManualClock(System.DateTimeOffset.UtcNow));
            e.Report(SignalKind.UnpairedRemoteSession);
            Assert.Equal(RiskLevel.Low, e.Level);         // 单独不够 Elevated(30)
            e.Report(SignalKind.RemoteSession);
            Assert.Equal(RiskLevel.Elevated, e.Level);    // 25 + 10
        }
    }
}
