using System;
using System.Collections.Generic;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows;
using SteelGuard.AntiRpa.Windows.Protection;

namespace SteelGuard.Demo
{
    /// <summary>演示:受保护的销售订单网格 + 导出 + 风险面板。</summary>
    public sealed class MainForm : Form
    {
        private readonly SteelGuardHost _guard;
        private readonly ShieldedDataGridView _grid = new ShieldedDataGridView();
        private readonly Label _status = new Label();
        private readonly ListBox _signals = new ListBox();
        private readonly System.Windows.Forms.Timer _uiTimer = new System.Windows.Forms.Timer { Interval = 1000 };
        private readonly List<Dictionary<string, object?>> _rows = MakeRows(600);

        public MainForm(SteelGuardHost guard)
        {
            _guard = guard;
            Text = "钢贸 ERP - 销售订单(SteelGuard Demo)";
            Width = 1200; Height = 720;
            StartPosition = FormStartPosition.CenterScreen;

            // ---- 工具栏 ----
            var bar = new FlowLayoutPanel { Dock = DockStyle.Top, Height = 44, Padding = new Padding(6) };
            bar.Controls.Add(Btn("导出 Excel(CSV)", async (_, __) => await ExportAsync()));
            bar.Controls.Add(Btn("模拟:发现 UiPath 进程", (_, __) => _guard.Engine.Report(SignalKind.KnownAutomationProcess, "uirobot (demo)")));
            bar.Controls.Add(Btn("模拟:UIA 高频探测", (_, __) => _guard.Engine.Report(SignalKind.UiaProbing, "120 WM_GETOBJECT/min (demo)")));
            bar.Controls.Add(Btn("模拟:机器节律点击", (_, __) => _guard.Engine.Report(SignalKind.RoboticTiming, "cv=0.02 (demo)")));
            bar.Controls.Add(Btn("人工验证通过 / 清零", (_, __) => _guard.ChallengePassed()));
            bar.Controls.Add(Btn("解码剪贴板水印", (_, __) => DecodeClipboard()));
            Controls.Add(bar);

            // ---- 右侧风险面板 ----
            var right = new Panel { Dock = DockStyle.Right, Width = 340, Padding = new Padding(8) };
            _status.Dock = DockStyle.Top; _status.Height = 90; _status.Font = new Font("Microsoft YaHei UI", 10f);
            _signals.Dock = DockStyle.Fill; _signals.Font = new Font("Consolas", 9f);
            right.Controls.Add(_signals);
            right.Controls.Add(_status);
            Controls.Add(right);

            // ---- 受保护网格 ----
            _grid.Dock = DockStyle.Fill;
            _grid.Sensitivity = DataSensitivity.Confidential;
            _grid.DataSetName = "sales_order";
            _grid.SensitiveColumns = new[] { "customer_name", "contact_phone", "unit_price", "gross_profit" };
            _grid.ReadOnly = true; _grid.AllowUserToAddRows = false; _grid.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
            _grid.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            _grid.CopyIntercepted += (_, d) => _status.ForeColor = Color.Firebrick;
            Controls.Add(_grid);
            _grid.BringToFront();
            _grid.DataSource = ToTable(_rows);

            // ---- 接入防护 ----
            _guard.Protect(this);
            _guard.Engine.SignalReceived += (_, s) => BeginInvoke(new Action(() =>
            {
                _signals.Items.Insert(0, $"{DateTime.Now:HH:mm:ss} {s}");
                if (_signals.Items.Count > 200) _signals.Items.RemoveAt(_signals.Items.Count - 1);
            }));
            _guard.LevelChanged += (_, e) => BeginInvoke(new Action(() => _grid.Invalidate()));
            _uiTimer.Tick += (_, __) => RefreshStatus();
            _uiTimer.Start();
            RefreshStatus();
        }

        private void RefreshStatus()
        {
            var lvl = _guard.Engine.Level;
            _status.ForeColor = lvl switch
            {
                RiskLevel.Low => Color.SeaGreen, RiskLevel.Elevated => Color.DarkOrange,
                RiskLevel.High => Color.OrangeRed, _ => Color.DarkRed,
            };
            var bd = string.Join("  ", _guard.Engine.Breakdown().OrderByDescending(kv => kv.Value).Take(4).Select(kv => $"{kv.Key}:{kv.Value:0}"));
            var (perHour, rowsToday) = _guard.Exports.Usage();
            _status.Text = $"风险等级:{lvl}   分值:{_guard.Engine.Score:0.0}\n{bd}\n设备 {_guard.DeviceId}  导出 {perHour}/h  {rowsToday} 行/日";
        }

        private async System.Threading.Tasks.Task ExportAsync()
        {
            var d = await _guard.RequestExportAsync("sales_order", _rows.Count, DataSensitivity.Confidential, waitForApproval: TimeSpan.FromSeconds(0));
            if (!d.Allowed)
            {
                MessageBox.Show(d.Reason + "\n\n" + string.Join("\n", d.Explanations), "导出被拦截", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                return;
            }
            var wm = _guard.NewWatermark();
            var rows = _guard.PrepareExportRows(_rows, d, wm);

            using var dlg = new SaveFileDialog { Filter = "CSV|*.csv", FileName = $"sales_order_{DateTime.Now:yyyyMMdd_HHmm}.csv" };
            if (dlg.ShowDialog(this) != DialogResult.OK) return;

            var sb = new StringBuilder();
            sb.AppendLine(wm.VisibleText());
            var cols = rows[0].Keys.ToList();
            sb.AppendLine(string.Join(",", cols));
            foreach (var r in rows) sb.AppendLine(string.Join(",", cols.Select(c => Csv(r[c]))));
            File.WriteAllText(dlg.FileName, sb.ToString(), new UTF8Encoding(true));
            _guard.RecordExport("sales_order", rows.Count, wm);
            MessageBox.Show($"已导出 {rows.Count} 行(含隐形水印 + 蜜罐)。\n{d.Reason}\n{string.Join("\n", d.Explanations)}", "导出完成");
        }

        private void DecodeClipboard()
        {
            var text = Clipboard.ContainsText() ? Clipboard.GetText() : "";
            var marks = Watermark.Decode(text);
            MessageBox.Show(marks.Count == 0 ? "剪贴板中未发现隐形水印" : "隐形水印载荷(userId:exportId:seq):\n" + string.Join("\n", marks), "水印解码");
        }

        private static Button Btn(string text, EventHandler onClick)
        {
            var b = new Button { Text = text, AutoSize = true, Height = 30, Padding = new Padding(6, 0, 6, 0) };
            b.Click += onClick;
            return b;
        }

        private static string Csv(object? v)
        {
            var s = v?.ToString() ?? "";
            return s.Contains(',') || s.Contains('"') ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        private static System.Data.DataTable ToTable(List<Dictionary<string, object?>> rows)
        {
            var t = new System.Data.DataTable();
            foreach (var k in rows[0].Keys) t.Columns.Add(k, typeof(string));
            foreach (var r in rows) t.Rows.Add(r.Values.Select(v => (object)(v?.ToString() ?? "")).ToArray());
            return t;
        }

        private static List<Dictionary<string, object?>> MakeRows(int n)
        {
            var rng = new Random(7);
            string[] cust = { "上海鑫源钢铁贸易有限公司", "无锡华达金属材料有限公司", "佛山恒丰物资有限公司", "唐山泰邦钢材加工有限公司", "杭州中诚实业有限公司" };
            string[] grade = { "Q235B", "Q355B", "HRB400E", "SPCC", "DC01" };
            string[] spec = { "3.0*1500*C", "5.75*1500*C", "Φ12", "Φ16", "8*1500*6000" };
            var list = new List<Dictionary<string, object?>>();
            for (int i = 0; i < n; i++)
            {
                var tons = Math.Round(5 + rng.NextDouble() * 80, 3);
                var price = 3400 + rng.Next(1200);
                list.Add(new Dictionary<string, object?>
                {
                    ["order_no"] = $"SO2609{i:D5}",
                    ["order_date"] = DateTime.Today.AddDays(-rng.Next(30)).ToString("yyyy-MM-dd"),
                    ["customer_name"] = cust[rng.Next(cust.Length)],
                    ["contact_phone"] = "13" + rng.Next(100000000, 999999999),
                    ["material_grade"] = grade[rng.Next(grade.Length)],
                    ["spec"] = spec[rng.Next(spec.Length)],
                    ["tonnage"] = tons,
                    ["unit_price"] = price,
                    ["amount"] = Math.Round(tons * price, 2),
                    ["gross_profit"] = Math.Round(tons * (rng.Next(-30, 120)), 2),
                });
            }
            return list;
        }
    }
}
