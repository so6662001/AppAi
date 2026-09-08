Imports System.Drawing
Imports System.Windows.Forms
Imports SteelGuard.AntiRpa.Core.Risk
Imports SteelGuard.AntiRpa.Core.Protection
Imports SteelGuard.AntiRpa.RdpLauncher

Namespace VbNetRdpLauncher
    ''' <summary>
    ''' 自研 RDP 启动器示例。接入 SteelGuard 只需四步:
    '''   1. Load 时 RdpLauncherGuard.Start(Me, opts)        —— 本地钩子 / 进程扫描 / 防截屏 / 遥测
    '''   2. Connect 前 Await guard.PrepareConnectAsync(rdp)  —— 申请票据 + 加固控件 + StartProgram
    '''   3. 登录完成后 guard.VerifyAfterConnect(rdp)          —— 复核重定向仍关闭
    '''   4. 订阅 guard.DisconnectRequested                    —— 风险达阈值自动断连时提示用户
    ''' </summary>
    Public Class MainForm
        Inherits Form

        Private WithEvents BtnConnect As New Button()
        Private ReadOnly TxtServer As New TextBox()
        Private ReadOnly TxtUser As New TextBox()
        Private ReadOnly TxtPwd As New TextBox()
        Private ReadOnly LblStatus As New Label()
        Private ReadOnly Rdp As New RdpAxHost()
        Private WithEvents StateTimer As New Timer()

        Private _guard As RdpLauncherGuard
        Private _wasConnected As Boolean

        Public Sub New()
            Text = "钢贸 ERP 远程登录"
            Size = New Size(1280, 800)
            StartPosition = FormStartPosition.CenterScreen

            Dim top As New FlowLayoutPanel() With {.Dock = DockStyle.Top, .Height = 36, .Padding = New Padding(6, 4, 6, 4)}
            TxtServer.Width = 180 : TxtServer.PlaceholderText = "服务器 (rds.example.com)"
            TxtUser.Width = 140 : TxtUser.PlaceholderText = "域\用户名"
            TxtPwd.Width = 140 : TxtPwd.PlaceholderText = "密码" : TxtPwd.UseSystemPasswordChar = True
            BtnConnect.Text = "连接"
            LblStatus.AutoSize = True : LblStatus.Padding = New Padding(12, 6, 0, 0)
            top.Controls.AddRange({TxtServer, TxtUser, TxtPwd, BtnConnect, LblStatus})

            Rdp.Dock = DockStyle.Fill
            Controls.Add(Rdp)
            Controls.Add(top)

            StateTimer.Interval = 1000
        End Sub

        Protected Overrides Sub OnLoad(e As EventArgs)
            MyBase.OnLoad(e)
            ' ---- 1. 启动本地防护 ----
            _guard = RdpLauncherGuard.Start(Me, New RdpLauncherOptions With {
                .TenantId = 1001,
                .UserId = 42,
                .UserName = Environment.UserName,
                .PolicyEndpoint = "https://api.example.com/v1/client-guard",   ' 为空 = 离线模式
                .ApiToken = "dev-token",
                .ErpStartProgram = "C:\SteelERP\SteelErp.exe",                 ' 服务器上的 ERP 路径 → 只发布程序,不给桌面
                .ErpWorkDir = "C:\SteelERP",
                .FailClosed = False
            })
            AddHandler _guard.DisconnectRequested, AddressOf OnGuardDisconnect
            AddHandler _guard.Host.LevelChanged, Sub(s, a) BeginInvoke(Sub() ShowStatus($"风险: {a.Current} ({a.Score:F0})"))
            ShowStatus("防护已启动,风险: Low")
            StateTimer.Start()
        End Sub

        Private Async Sub BtnConnect_Click(sender As Object, e As EventArgs) Handles BtnConnect.Click
            BtnConnect.Enabled = False
            Try
                ' ---- 2. Connect 前:申请票据 + 加固控件(剪贴板 / 驱动器 / StartProgram 等) ----
                Dim r = Await _guard.PrepareConnectAsync(Rdp)
                If Not r.CanConnect Then
                    MessageBox.Show(Me, r.DenyReason, "无法连接", MessageBoxButtons.OK, MessageBoxIcon.Warning)
                    Return
                End If

                Dim ocx = Rdp.Rdp                      ' 后期绑定:老项目通常是 AxRdp.Server / AxRdp.UserName ...
                ocx.Server = TxtServer.Text
                ocx.UserName = TxtUser.Text
                ocx.AdvancedSettings9.ClearTextPassword = TxtPwd.Text
                ocx.Connect()
                ShowStatus($"连接中… 剪贴板={(If(r.ClipboardAllowed, "开", "关"))} 票据={(If(r.Ticket Is Nothing, "无(离线)", "已绑定"))}")
            Catch ex As Exception
                MessageBox.Show(Me, ex.Message, "连接失败", MessageBoxButtons.OK, MessageBoxIcon.Error)
            Finally
                BtnConnect.Enabled = True
            End Try
        End Sub

        ''' <summary>
        ''' 用 AxInterop 时请直接订阅 OnLoginComplete / OnDisconnected;这里为了不依赖 Interop 用定时器轮询 Connected 状态。
        ''' </summary>
        Private Sub StateTimer_Tick(sender As Object, e As EventArgs) Handles StateTimer.Tick
            Dim st = RdpControlHardening.ConnectionState(Rdp)
            Dim connected = (st = 1)
            If connected AndAlso Not _wasConnected Then
                ' ---- 3. 登录完成:复核加固没被改掉 ----
                If Not _guard.VerifyAfterConnect(Rdp) Then ShowStatus("警告:重定向设置被篡改,已上报")
            End If
            _wasConnected = connected
        End Sub

        ''' <summary>4. 风险达到阈值,SDK 已断开 RDP,这里只负责提示。</summary>
        Private Sub OnGuardDisconnect(sender As Object, reason As String)
            ShowStatus(reason)
            MessageBox.Show(Me, reason & vbCrLf & "如为误判,请联系管理员解除。", "会话已断开", MessageBoxButtons.OK, MessageBoxIcon.Stop)
        End Sub

        Private Sub ShowStatus(s As String)
            LblStatus.Text = s
        End Sub

        Protected Overrides Sub OnFormClosed(e As FormClosedEventArgs)
            StateTimer.Stop()
            _guard?.Dispose()
            MyBase.OnFormClosed(e)
        End Sub
    End Class
End Namespace
