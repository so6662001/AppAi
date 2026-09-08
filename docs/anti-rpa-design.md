# ERP 客户端防 RPA / 防自动化爬取 (Anti-RPA) 设计

> 适用对象:C# (WinForms / WPF) ERP 客户端 + 服务端配套。
> 代码位置:`apps/erp-client-guard/` (C# SDK + Demo + 单元测试),`services/client-guard-service/` (服务端策略 / 遥测 / 导出审批),`ddl/22_client_guard.sql`。

---

## 1. 威胁模型

| 编号 | 攻击手法 | 典型工具 | 特征 |
|---|---|---|---|
| T1 | **UI Automation / MSAA 读取控件树** | UiPath、影刀、来也 UiBot、Power Automate Desktop、云扩、艺赛旗、pywinauto、FlaUI、Inspect.exe | 目标进程收到大量 `WM_GETOBJECT`;`UIAutomationCore.dll` 被注入加载;无鼠标键盘动作却能读到整表数据 |
| T2 | **模拟键鼠 + 剪贴板** | 按键精灵、AutoHotkey、AutoIt、pyautogui、影刀(图像模式) | `SendInput` 注入输入 (`LLKHF_INJECTED`);点击间隔方差极小;鼠标"瞬移";高频 Ctrl+A / Ctrl+C;固定节拍翻页 |
| T3 | **调用客户端自带"导出 Excel"** | 任意 RPA | 短时间内大量导出、导出行数异常、非工作时间导出 |
| T4 | **截屏 + OCR** | 影刀图像模式、Sikuli、AI 电脑操控 Agent ("龙虾" OpenClaw/Clawdbot 类、Computer-Use 类 Agent) | 频繁截屏 (`BitBlt/PrintWindow`);Agent 进程驻留;视觉识别后再注入输入 |
| T5 | **直接调接口 / 抓包重放** | Fiddler、mitmproxy、自写脚本 | 绕过客户端,直接打后端 API |
| T6 | **远程桌面外包操作** | TeamViewer、AnyDesk、ToDesk、向日葵、RustDesk | RDP/远控会话;人肉或 RPA 在远端操作 |

结论:**单靠客户端无法 100% 防御 T4/T5**(拍照都能拿走屏幕内容),但可以做到:

1. 把 T1/T2/T3 的**成本从"零"提高到"不划算"**(自动化 100% 失效或触发封禁);
2. 数据一旦泄露**可追溯到人**(水印 + 蜜罐);
3. **服务端**对导出/查询做硬性配额与审批,不信任客户端。

## 2. 分层防御(纵深)

```
┌──────────────────────────────────────────────────────────────────┐
│  L5 服务端硬约束   导出配额 / 审批 token / 行数上限 / 异常账号封禁   │  ← 不可绕过
├──────────────────────────────────────────────────────────────────┤
│  L4 可追溯         可见水印 + 零宽字符隐形水印 + 蜜罐行 (HMAC 可回溯) │
├──────────────────────────────────────────────────────────────────┤
│  L3 数据面降级     风险升高 → 敏感列脱敏 / 禁复制 / 禁导出 / 人机挑战  │
├──────────────────────────────────────────────────────────────────┤
│  L2 UI 抗自动化    隐藏 UIA/MSAA 控件树 / 虚拟化网格 / 防截屏窗口属性  │
├──────────────────────────────────────────────────────────────────┤
│  L1 检测与评分     进程 / 注入输入 / WM_GETOBJECT / 行为节律 / 环境    │
└──────────────────────────────────────────────────────────────────┘
```

### L1 检测信号 (`SteelGuard.AntiRpa.Windows/Detection`)

| 信号 | 实现 | 权重 | 备注 |
|---|---|---|---|
| `KnownAutomationProcess` | 周期扫描进程名(60+ 已知 RPA / Agent / 远控),服务端可下发增量名单 | 25~40 | 远控工具权重低于 RPA |
| `InjectedInput` | `WH_KEYBOARD_LL` / `WH_MOUSE_LL` 钩子读取 `LLKHF_INJECTED` / `LLMHF_INJECTED` | 每次 3,上限 40 | RDP 会话所有输入都是"注入",自动降权 |
| `UiaProbing` | 子类化窗口 `WndProc` 统计 `WM_GETOBJECT`(区分 `UiaRootObjectId=-25` / `OBJID_CLIENT=-4`) | 频率超阈值 20~35 | 读屏软件会误报,可白名单 (NVDA/JAWS/讲述人) |
| `UiaCoreLoaded` | 启动基线后 `UIAutomationCore.dll` 被外部加载进本进程 | 20 | 强信号 |
| `RoboticTiming` | 事件间隔变异系数 CV < 0.08 且样本 ≥ 12 | 20 | 人类 CV 一般 > 0.3 |
| `TeleportClick` | 点击前 300ms 无移动却位移 > 200px | 每次 4 | 真实鼠标必有轨迹 |
| `RepeatedExactClick` | 同一像素点击 ≥ 8 次 | 10 | |
| `SuperhumanRate` | 按键 > 15/s 或 操作 > 6/s 持续 | 15 | 排除长按重复 |
| `RhythmicPaging` | 翻页动作固定节拍 (CV<0.1, ≥ 6 页) | 20 | 爬全表签名 |
| `ClipboardBurst` | 60s 内复制 ≥ 10 次 | 15 | `WM_CLIPBOARDUPDATE` |
| `RemoteSession` | `GetSystemMetrics(SM_REMOTESESSION)` / 远控进程 | 10 | 组合信号 |
| `DebuggerAttached` | `IsDebuggerPresent` / `CheckRemoteDebuggerPresent` | 30 | |
| `VirtualMachine` | Hypervisor 进程 / BIOS 厂商 | 5 | 仅辅助 |

### 风险引擎 (`SteelGuard.AntiRpa.Core/Risk`)

- 每个信号带 **权重 + 半衰期**,得分 = Σ weight × 0.5^(elapsed/halfLife),上限 100。
- 等级:`Low <30` → `Elevated 30~60` → `High 60~85` → `Critical ≥85`。
- 等级 → 动作 (`PolicyEngine`, 服务端可下发覆盖):

| 等级 | 导出 | 复制 | 网格 | 其他 |
|---|---|---|---|---|
| Low | 允许 + 水印 | 允许 | 正常 | 上报 |
| Elevated | 行数上限减半 + 强制延迟 2~5s | 每次 ≤ 50 行 | 隐藏 UIA 树 | 上报 |
| High | 需人机挑战 + 服务端审批 | 禁止 | 敏感列脱敏 | 弹窗提示 |
| Critical | 禁止 | 禁止 | 全脱敏 | 会话锁定 + 服务端告警 |

### L2 UI 抗自动化 (`ShieldedDataGridView` / `ScreenCaptureGuard`)

- **隐藏控件树**:重写 `CreateAccessibilityInstance` 返回无子节点的 `AccessibleObject`,并在 `WndProc` 中对 `WM_GETOBJECT(UiaRootObjectId)` 返回 0。UiPath/影刀"选择器"模式将只看到一个不透明矩形。
- **虚拟模式**:`VirtualMode = true`,只有可视行在内存 / 控件里,无法一次性"读全表"。
- **防截屏**:`SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE)`(Win10 2004+,老系统退化到 `WDA_MONITOR`)。截屏/录屏/远控画面为黑块,对图像识别类 RPA 与 Computer-Use Agent 有效。
- **快捷键拦截**:`Ctrl+A / Ctrl+C / Ctrl+Insert / Shift+Insert` 走 `ClipboardGuard` 审计。

### L3 数据面降级 (`DataMasker` / `ClipboardGuard` / `ExportGovernor`)

- 敏感列(客户名、电话、单价、毛利)按等级脱敏:`张*` / `138****1234` / `¥ ***`。
- 剪贴板:限制行数、追加水印行、高风险直接清空。
- 导出:滑动窗口配额(次数/小时、行数/天)、单次行数上限、超阈值需服务端 **审批 token(HMAC-SHA256,含 用户/行数/过期时间)**、随机延迟打乱脚本节拍。

### L4 可追溯 (`Watermark` / `CanaryData`)

- **可见水印**:导出文件首行/页脚 `导出:张三(1023) 2026-09-08 14:05 设备 A1B2 单号 7f3e…`。
- **隐形水印**:在文本列插入零宽字符 (`U+200B/U+200C/U+200D`) 编码 `userId + 序号`,复制粘贴到 Excel/微信仍保留,肉眼不可见,`Watermark.Decode()` 可还原。
- **蜜罐行**:按 HMAC(tenant,user,day) 生成 1~3 条"看起来真实"的客户/订单,业务上不存在;一旦在外部出现即可定位泄露账号与日期。

### L5 服务端 (`services/client-guard-service`)

- `GET /v1/policy`:下发阈值、配额、进程名单、敏感列;客户端每 10 分钟拉取。
- `POST /v1/events`:批量遥测,服务端**独立**再评分(客户端得分只是参考,可被篡改;服务端还能看到跨设备并发、账本超配额、非工作时间批量导出等客户端看不到的信号);返回 `directive`(`none / degrade / lock`)。
- `POST /v1/export/request`:服务端配额检查 → 低风险小批量自动签发 token;否则进入审批,主管在 registry-web 审批。
- `POST /v1/export/consume`:业务后端在真正生成 Excel 前校验并一次性消费 token(**这一步必须在你们 Java/ERP 后端落地,否则 L1~L4 都能被绕过**)。
- 表结构:`ddl/22_client_guard.sql`(策略 / 事件 / 导出申请 / 配额账本 / 设备指令)。

## 3. 局限与坦诚说明

1. **拍照 / 外接摄像头 / 人肉抄录** 无法阻止 —— 只能靠水印 + 蜜罐追责。
2. **内核级注入 (驱动模拟硬件输入)** 不带 `INJECTED` 标志 —— 靠行为节律 + 服务端配额兜底。
3. **读屏软件用户**(视障员工)会触发 UIA 信号 —— 提供白名单进程与"无障碍模式"开关。
4. **RDP 环境**输入全部是注入 —— 自动识别远程会话后将 `InjectedInput` 权重降到 0.2 倍。
5. 所有客户端检测都可被逆向 —— 建议对 SDK 程序集做混淆 + 强命名,并把决策阈值放服务端。
6. 合规:进程扫描仅读取进程名(不读取内存/文件),遥测不上传屏幕内容;需在员工手册中告知。

## 4. 接入步骤 (WinForms 示例)

```csharp
// Program.cs(登录成功后,UI 线程)
var guard = SteelGuardHost.Start(new GuardOptions {
    TenantId = 1001, UserId = 1023, UserName = "张三",
    PolicyEndpoint = "https://api.example.com/v1/client-guard",
    ApiToken = jwt, CanarySecret = "<与服务端一致>",
});
guard.ChallengeHandler = d => ShowSliderCaptchaAsync(d);      // 人机挑战
guard.SessionLockRequested += (_, msg) => ForceLogout(msg);   // Critical → 锁定

// 主窗体
guard.Protect(this);                       // 防截屏 + WM_GETOBJECT 探针 + 按等级隐藏 UIA 树

// 敏感网格换成 ShieldedDataGridView(设计器里改基类即可)
gridOrders.Sensitivity = DataSensitivity.Confidential;
gridOrders.DataSetName = "sales_order";
gridOrders.SensitiveColumns = new[] { "customer_name", "unit_price", "gross_profit" };

// 导出按钮
var d = await guard.RequestExportAsync("sales_order", rows.Count, DataSensitivity.Confidential,
                                       waitForApproval: TimeSpan.FromMinutes(2));
if (!d.Allowed) { MessageBox.Show(d.Reason); return; }
var wm   = guard.NewWatermark();
var safe = guard.PrepareExportRows(rows, d, wm);   // 截断 → 脱敏 → 隐形水印 → 蜜罐
ExcelWriter.Write(safe, header: wm.VisibleText());
guard.RecordExport("sales_order", safe.Count, wm);
```

完整目录与 WPF 适配说明见 [`apps/erp-client-guard/README.md`](../apps/erp-client-guard/README.md)。

## 5. 与现有平台的关系

- 遥测事件写入 MySQL `client_guard_event`,可作为 `risk-alert-service` 的一个数据源("同一账号 1 小时导出 > 10 万行"进入老板风险简报)。
- 审批流复用 `registry-web`(新增"导出审批"菜单),审批人默认为部门经理(`role_profile` 中 `TRADE_SALES_MGR` 等)。
