Imports System.Windows.Forms
Imports SteelGuard.AntiRpa.Core.Protection
Imports SteelGuard.AntiRpa.RdpLauncher

Namespace VbNetRdpLauncher
    ''' <summary>
    ''' 不依赖 AxInterop.MSTSCLib 的 RDP 控件宿主(直接用 CLSID 创建 MsRdpClient9NotSafeForScripting)。
    ''' 如果你的项目已经通过工具箱添加了 AxMsRdpClient9NotSafeForScripting,直接用那个控件即可,
    ''' SteelGuard 接口同时接受 AxHost 或 GetOcx() 返回的对象。
    ''' </summary>
    Public Class RdpAxHost
        Inherits AxHost

        Public Sub New()
            MyBase.New(RdpControlHardening.Clsid_MsRdpClient9NotSafeForScripting)
        End Sub

        ''' <summary>后期绑定访问 COM 对象(Option Strict Off)。</summary>
        Public ReadOnly Property Rdp As Object
            Get
                Return GetOcx()
            End Get
        End Property
    End Class
End Namespace
