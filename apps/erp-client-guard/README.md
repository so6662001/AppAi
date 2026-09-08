# SteelGuard.AntiRpa — ERP 客户端防 RPA / 防自动化爬取 SDK (C#)

> 设计说明见 [`docs/anti-rpa-design.md`](../../docs/anti-rpa-design.md);服务端见 [`services/client-guard-service`](../../services/client-guard-service)。

```
apps/erp-client-guard/
├── SteelGuard.sln
├── src/
│   ├── SteelGuard.AntiRpa.Core/       netstandard2.0 + net8.0 — 平台无关纯逻辑(可单测)
│   │   ├── Core/Signals.cs            信号类型 / 风险等级 / 时钟抽象
│   │   ├── Risk/GuardPolicy.cs        策略(阈值、权重、配额、进程名单、敏感列;服务端 JSON 下发)
│   │   ├── Risk/RiskEngine.cs         评分引擎:权重 × 半衰期衰减 × 同类上限
│   │   ├── Risk/PolicyEngine.cs       (等级, 操作, 敏感级, 行数) → 动作集合
│   │   ├── Detection/BehaviorAnalyzer.cs   节律 CV / 瞬移 / 超人速率 / 翻页节拍 / 剪贴板突发
│   │   ├── Detection/ProcessMatcher.cs     进程名分类(RPA / 远控 / 读屏)
│   │   ├── Protection/ExportGovernor.cs    导出配额 + 审批 token 校验
│   │   ├── Protection/ApprovalToken.cs     HMAC-SHA256 审批 token(与 Python 服务端二进制兼容)
│   │   ├── Protection/Watermark.cs         可见水印 + 零宽字符隐形水印(编码/解码/剥离)
│   │   ├── Protection/CanaryData.cs        确定性蜜罐行(HMAC 派生,可溯源)
│   │   ├── Protection/DataMasker.cs        敏感列脱敏
│   │   └── Telemetry/Telemetry.cs          事件模型 + HTTP 批量上报 / 本地 jsonl 兜底
│   ├── SteelGuard.AntiRpa.Windows/    net48 + net8.0-windows — Windows / WinForms 实现
│   │   ├── Native/NativeMethods.cs         P/Invoke
│   │   ├── Detection/InputInjectionMonitor.cs  WH_KEYBOARD_LL / WH_MOUSE_LL 读取 INJECTED 标志
│   │   ├── Detection/UiAutomationProbe.cs      WM_GETOBJECT 统计 + UIAutomationCore.dll 加载检测 + 可屏蔽 UIA 根
│   │   ├── Detection/EnvironmentProbe.cs       进程扫描 / RDP / 调试器 / 虚拟机
│   │   ├── Protection/ScreenCaptureGuard.cs    SetWindowDisplayAffinity 防截屏
│   │   ├── Protection/ClipboardGuard.cs        WM_CLIPBOARDUPDATE 计数
│   │   ├── Protection/ShieldedDataGridView.cs  网格护盾(隐藏 UIA 树 / 受控复制 / 显示层脱敏 / 水印)
│   │   ├── GuardApiClient.cs               服务端 API 客户端 + 远程 token 校验
│   │   └── SteelGuardHost.cs               门面:一行启动,Protect(form) / Decide / RequestExportAsync
│   └── SteelGuard.Demo/               WinForms 演示程序
└── tests/SteelGuard.Tests/            xUnit,67 个用例(Core 纯逻辑 + 跨语言 token 向量)
```

## 构建 / 测试

```bash
dotnet build SteelGuard.sln -c Release          # Linux/macOS 也能编译(EnableWindowsTargeting)
dotnet test  tests/SteelGuard.Tests -c Release  # 67 passed
dotnet run --project src/SteelGuard.Demo        # 仅 Windows
```

Demo 运行时可设置 `STEELGUARD_ENDPOINT=http://localhost:8980/v1`(经网关则为 `https://api/v1/client-guard`)与 `STEELGUARD_TOKEN=<jwt>` 联调服务端;不设置则为离线模式(内置默认策略 + `%LocalAppData%\SteelGuard\events.jsonl`)。

## 接入现有 WinForms 客户端(5 步)

```csharp
// 1. 登录成功后,UI 线程启动
var guard = SteelGuardHost.Start(new GuardOptions {
    TenantId = tenantId, UserId = userId, UserName = userName,
    PolicyEndpoint = baseUrl + "/v1/client-guard", ApiToken = jwt,
    CanarySecret = "<与服务端一致>",
});

// 2. 人机挑战 & 锁定回调
guard.ChallengeHandler = d => ShowSliderCaptchaAsync(d);          // 返回 Task<bool>
guard.SessionLockRequested += (_, msg) => ForceLogout(msg);

// 3. 每个业务窗体
guard.Protect(this);

// 4. 敏感网格:设计器里把 DataGridView 基类改为 ShieldedDataGridView
gridOrders.Sensitivity = DataSensitivity.Confidential;
gridOrders.DataSetName = "sales_order";
gridOrders.SensitiveColumns = new[] { "customer_name", "contact_phone", "unit_price", "gross_profit" };

// 5. 导出按钮
var d = await guard.RequestExportAsync("sales_order", rows.Count, DataSensitivity.Confidential,
                                       waitForApproval: TimeSpan.FromMinutes(2));
if (!d.Allowed) { MessageBox.Show(d.Reason); return; }
var wm   = guard.NewWatermark();
var safe = guard.PrepareExportRows(rows, d, wm);   // 截断 → 脱敏 → 隐形水印 → 蜜罐
ExcelWriter.Write(safe, header: wm.VisibleText());
guard.RecordExport("sales_order", safe.Count, wm);
```

WPF 客户端:`Core` 直接复用;`Windows` 中的钩子 / 探针 / 防截屏均基于 HWND,用 `WindowInteropHelper` 取句柄即可;`ShieldedDataGridView` 需按 `DataGrid` 重写 `OnCreateAutomationPeer` 返回空 peer(思路相同)。

## 后端必须落地的两件事(否则客户端防护可被绕过)

1. **导出接口校验 token**:ERP 后端在真正生成 Excel 前调用 `POST /v1/client-guard/export/consume`(一次性消费 + 记账),token 无效则拒绝。小批量导出完成后调用 `POST /v1/client-guard/export/record` 记账。
2. **查询接口限流**:列表 / 分页查询按用户做行数配额(RPA 翻页爬全表本质是打查询接口)。

## 泄露溯源

- 拿到外泄 Excel → 任一文本单元格 `Watermark.Decode()` → `userId:exportId:seq`。
- 或在服务端按 (tenant, user, day) 重算蜜罐 `CanaryData.Generate()`,与外泄记录比对 `Matches()`。

## 已知局限

拍照 / OCR、驱动级输入模拟、逆向 SDK 无法完全阻止;详见设计文档第 3 节。建议对 SDK 做混淆 + 强命名,并把阈值放在服务端策略里。
