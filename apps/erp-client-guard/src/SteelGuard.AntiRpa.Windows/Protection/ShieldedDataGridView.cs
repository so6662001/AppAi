using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Linq;
using System.Text;
using System.Windows.Forms;
using SteelGuard.AntiRpa.Core;
using SteelGuard.AntiRpa.Core.Detection;
using SteelGuard.AntiRpa.Core.Protection;
using SteelGuard.AntiRpa.Core.Risk;
using SteelGuard.AntiRpa.Windows.Native;

namespace SteelGuard.AntiRpa.Windows.Protection
{
    /// <summary>
    /// 带护盾的 DataGridView。在设计器里把基类从 DataGridView 改为本类即可。
    /// <list type="bullet">
    /// <item>隐藏 UIA / MSAA 控件树:RPA "选择器"只能看到一个不透明矩形,读不到单元格;</item>
    /// <item>复制走策略:限制行数 / 附加隐形水印 / 高风险时禁止;</item>
    /// <item>风险升高时敏感列自动脱敏(只影响显示,不改数据源);</item>
    /// <item>翻页节律上报(PageDown / 滚轮整页)用于识别爬全表;</item>
    /// <item>机密级别网格叠加半透明可见水印。</item>
    /// </list>
    /// </summary>
    public class ShieldedDataGridView : DataGridView
    {
        private SteelGuardHost? _guard;
        private string[] _sensitiveColumns = Array.Empty<string>();
        private HashSet<string> _sensitiveSet = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        private int _lastFirstRow = -1;

        public ShieldedDataGridView()
        {
            // 减少 UIA 暴露的属性
            AccessibleRole = AccessibleRole.Graphic;
            ClipboardCopyMode = DataGridViewClipboardCopyMode.EnableWithoutHeaderText;
            DoubleBuffered = true;
        }

        /// <summary>数据敏感级别,影响脱敏与水印。</summary>
        [Category("SteelGuard"), DefaultValue(DataSensitivity.Internal)]
        public DataSensitivity Sensitivity { get; set; } = DataSensitivity.Internal;

        /// <summary>敏感列名(DataPropertyName 或 Column.Name)。为空则使用策略下发的全局敏感列。</summary>
        [Category("SteelGuard")]
        public string[] SensitiveColumns
        {
            get => _sensitiveColumns;
            set
            {
                _sensitiveColumns = value ?? Array.Empty<string>();
                _sensitiveSet = new HashSet<string>(_sensitiveColumns, StringComparer.OrdinalIgnoreCase);
                Invalidate();
            }
        }

        /// <summary>数据集名称(用于遥测 / 导出审批)。</summary>
        [Category("SteelGuard")]
        public string DataSetName { get; set; } = "";

        /// <summary>始终隐藏 UIA 树(默认:仅当风险 ≥ Elevated 或敏感级 ≥ Confidential 时隐藏)。</summary>
        [Category("SteelGuard"), DefaultValue(false)]
        public bool AlwaysHideAccessibilityTree { get; set; }

        /// <summary>显示可见水印(默认在 Confidential 及以上自动开启)。</summary>
        [Category("SteelGuard"), DefaultValue(false)]
        public bool ShowVisibleWatermark { get; set; }

        [Browsable(false), DesignerSerializationVisibility(DesignerSerializationVisibility.Hidden)]
        public SteelGuardHost? Guard
        {
            get => _guard ?? SteelGuardHost.Current;
            set => _guard = value;
        }

        /// <summary>复制被策略拒绝 / 截断时触发,宿主可弹提示。</summary>
        public event EventHandler<GuardDecision>? CopyIntercepted;

        // ------------------------------------------------------------------
        private bool HideTree
        {
            get
            {
                var g = Guard;
                if (g != null && g.Policy.AccessibilityMode) return false;
                if (AlwaysHideAccessibilityTree) return true;
                if (Sensitivity >= DataSensitivity.Confidential) return true;
                return g != null && g.Engine.Level >= RiskLevel.Elevated;
            }
        }

        private IEnumerable<string> EffectiveSensitiveColumns =>
            _sensitiveColumns.Length > 0 ? _sensitiveColumns : (Guard?.Policy.SensitiveColumns ?? new List<string>());

        private bool ShouldMask
        {
            get
            {
                var g = Guard;
                if (g == null) return false;
                var d = PolicyEngine.Decide(g.Policy, g.Engine.Level, g.Engine.Score, GuardOperation.View, Sensitivity);
                return d.Has(GuardAction.Mask);
            }
        }

        // ---------------- UIA / MSAA ----------------
        protected override AccessibleObject CreateAccessibilityInstance() =>
            HideTree ? new OpaqueAccessibleObject(this) : base.CreateAccessibilityInstance();

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == NativeMethods.WM_GETOBJECT)
            {
                Guard?.UiaProbe?.OnGetObject(m.LParam);
                var objId = unchecked((int)m.LParam.ToInt64());
                if (HideTree && (objId == NativeMethods.UiaRootObjectId))
                {
                    m.Result = IntPtr.Zero;
                    return;
                }
            }
            base.WndProc(ref m);
        }

        /// <summary>不暴露任何子对象 / 名称 / 值的无障碍对象。</summary>
        private sealed class OpaqueAccessibleObject : Control.ControlAccessibleObject
        {
            public OpaqueAccessibleObject(Control owner) : base(owner) { }
            public override AccessibleRole Role => AccessibleRole.Graphic;
            public override string Name => "受保护的数据区域";
            public override string? Value { get => null; set { } }
            public override string? Description => null;
            public override int GetChildCount() => 0;
            public override AccessibleObject? GetChild(int index) => null;
            public override AccessibleObject? GetFocused() => null;
            public override AccessibleObject? GetSelected() => null;
            public override AccessibleObject? HitTest(int x, int y) => this;
            public override AccessibleObject? Navigate(AccessibleNavigation navdir) => null;
        }

        // ---------------- 复制 ----------------
        protected override bool ProcessCmdKey(ref Message msg, Keys keyData)
        {
            var isCopy = keyData == (Keys.Control | Keys.C) || keyData == (Keys.Control | Keys.Insert);
            var isSelectAll = keyData == (Keys.Control | Keys.A);
            var isPage = keyData == Keys.PageDown || keyData == Keys.PageUp || keyData == (Keys.Control | Keys.End);

            if (isPage) Guard?.Analyzer.Feed(new InputEvent(InputEventType.PageTurn, Guard.Clock.Now));

            if (isCopy) { DoGuardedCopy(); return true; }

            if (isSelectAll)
            {
                var g = Guard;
                if (g != null && g.Engine.Level >= RiskLevel.Elevated)
                {
                    // 高风险时 Ctrl+A 只选中可见行
                    ClearSelection();
                    var first = FirstDisplayedScrollingRowIndex;
                    var n = DisplayedRowCount(true);
                    for (int i = first; i >= 0 && i < Rows.Count && i < first + n; i++) Rows[i].Selected = true;
                    return true;
                }
            }
            return base.ProcessCmdKey(ref msg, keyData);
        }

        /// <summary>按策略复制选中单元格(可由右键菜单调用)。</summary>
        public void DoGuardedCopy()
        {
            var g = Guard;
            if (g == null) { CopyDefault(); return; }

            var d = g.Decide(GuardOperation.Copy, Sensitivity, SelectedRowCount());
            if (!d.Allowed)
            {
                CopyIntercepted?.Invoke(this, d);
                g.Emit("decision", d, DataSetName);
                return;
            }
            var text = BuildTsv(d.RowLimit, d.Has(GuardAction.Mask), d.Has(GuardAction.Watermark) ? g.NewWatermark() : null);
            if (text.Length == 0) return;
            try { Clipboard.SetText(text); } catch { /* 剪贴板被占用 */ }
            if (d.RowLimit > 0 && SelectedRowCount() > d.RowLimit) CopyIntercepted?.Invoke(this, d);
            g.Emit("copy", d, DataSetName);
        }

        private void CopyDefault()
        {
            var obj = GetClipboardContent();
            if (obj != null) Clipboard.SetDataObject(obj);
        }

        private int SelectedRowCount()
        {
            if (SelectedRows.Count > 0) return SelectedRows.Count;
            return SelectedCells.Cast<DataGridViewCell>().Select(c => c.RowIndex).Distinct().Count();
        }

        private string BuildTsv(int rowLimit, bool mask, WatermarkContext? wm)
        {
            var rows = SelectedCells.Cast<DataGridViewCell>()
                .Where(c => c.RowIndex >= 0 && c.OwningColumn.Visible)
                .GroupBy(c => c.RowIndex).OrderBy(g => g.Key).ToList();
            if (rowLimit > 0 && rows.Count > rowLimit) rows = rows.Take(rowLimit).ToList();
            var sensitive = new HashSet<string>(EffectiveSensitiveColumns, StringComparer.OrdinalIgnoreCase);

            var sb = new StringBuilder();
            int seq = 0;
            foreach (var g in rows)
            {
                var cells = g.OrderBy(c => c.OwningColumn.DisplayIndex).ToList();
                bool marked = false;
                for (int i = 0; i < cells.Count; i++)
                {
                    var c = cells[i];
                    var col = c.OwningColumn.DataPropertyName ?? c.OwningColumn.Name;
                    var v = c.FormattedValue?.ToString() ?? "";
                    if (mask && (sensitive.Contains(col) || sensitive.Contains(c.OwningColumn.Name))) v = DataMasker.Mask(col, c.Value);
                    if (wm != null && !marked && v.Length > 1 && !double.TryParse(v, out _)) { v = Watermark.Mark(v, wm, seq++); marked = true; }
                    if (i > 0) sb.Append('\t');
                    sb.Append(v);
                }
                sb.AppendLine();
            }
            if (wm != null && rows.Count > 0) sb.AppendLine(wm.VisibleText());
            return sb.ToString();
        }

        // ---------------- 显示层脱敏 ----------------
        protected override void OnCellFormatting(DataGridViewCellFormattingEventArgs e)
        {
            base.OnCellFormatting(e);
            if (e.RowIndex < 0 || e.ColumnIndex < 0 || !ShouldMask) return;
            var col = Columns[e.ColumnIndex];
            var name = col.DataPropertyName ?? col.Name;
            if (EffectiveSensitiveColumns.Contains(name, StringComparer.OrdinalIgnoreCase) ||
                EffectiveSensitiveColumns.Contains(col.Name, StringComparer.OrdinalIgnoreCase))
            {
                e.Value = DataMasker.Mask(name, e.Value);
                e.FormattingApplied = true;
            }
        }

        // ---------------- 翻页 / 滚动节律 ----------------
        protected override void OnScroll(ScrollEventArgs e)
        {
            base.OnScroll(e);
            if (e.ScrollOrientation != ScrollOrientation.VerticalScroll) return;
            var page = Math.Max(1, DisplayedRowCount(false));
            if (_lastFirstRow >= 0 && Math.Abs(e.NewValue - _lastFirstRow) >= page - 1)
                Guard?.Analyzer.Feed(new InputEvent(InputEventType.PageTurn, Guard.Clock.Now));
            _lastFirstRow = e.NewValue;
        }

        // ---------------- 可见水印 ----------------
        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            if (!(ShowVisibleWatermark || Sensitivity >= DataSensitivity.Confidential)) return;
            var g = Guard;
            var text = g != null ? $"{g.Options.UserName} {g.Options.UserId} {DateTime.Now:MM-dd HH:mm}" : "内部资料";
            using var font = new Font(Font.FontFamily, 14f, FontStyle.Bold);
            using var brush = new SolidBrush(Color.FromArgb(22, 60, 60, 60));
            var state = e.Graphics.Save();
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            var size = e.Graphics.MeasureString(text, font);
            for (float y = -Height; y < Height * 2; y += size.Height * 6)
                for (float x = -Width; x < Width * 2; x += size.Width * 1.8f)
                {
                    e.Graphics.ResetTransform();
                    e.Graphics.TranslateTransform(x, y);
                    e.Graphics.RotateTransform(-25);
                    e.Graphics.DrawString(text, font, brush, 0, 0);
                }
            e.Graphics.Restore(state);
        }
    }
}
