using System;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows;

namespace SteelGuard.Demo
{
    internal static class Program
    {
        [STAThread]
        static void Main()
        {
            ApplicationConfiguration.Initialize();

            // 1. 启动防护(UI 线程)。PolicyEndpoint 为空 → 离线模式(默认策略 + 本地 jsonl 日志)
            var guard = SteelGuardHost.Start(new GuardOptions
            {
                TenantId = 1001,
                UserId = 1023,
                UserName = "张三",
                PolicyEndpoint = Environment.GetEnvironmentVariable("STEELGUARD_ENDPOINT"),   // 例: http://localhost:8980/v1
                ApiToken = Environment.GetEnvironmentVariable("STEELGUARD_TOKEN"),
                OfflineApprovalSecret = "demo-secret",
                CanarySecret = "demo-canary-secret",
                ClientVersion = "demo-0.1",
            });

            // 2. 人机挑战:这里用最简单的确认框代替拖动验证 / 二次登录
            guard.ChallengeHandler = d =>
            {
                var r = MessageBox.Show(
                    $"检测到异常操作(风险分 {d.Score:0})。\n\n{string.Join("\n", d.Explanations)}\n\n请确认是本人操作。",
                    "SteelGuard 人工验证", MessageBoxButtons.OKCancel, MessageBoxIcon.Warning);
                return System.Threading.Tasks.Task.FromResult(r == DialogResult.OK);
            };

            guard.SessionLockRequested += (_, msg) =>
            {
                MessageBox.Show(msg + "\n\n程序将退出。", "SteelGuard", MessageBoxButtons.OK, MessageBoxIcon.Stop);
                Application.Exit();
            };

            Application.Run(new MainForm(guard));
        }
    }
}
