# Luomu CAD 0.17.1 发布说明与验证范围

日期：2026-11-25

摘要：0.17.1 是修复版，解决了由 agent 启动 AutoCAD 时弹出 "Autodesk Error Report" 或启动失败的问题。不管启动请求来自哪个 agent 宿主，都会经过同一个修复点。没有新增绘图能力；0.17.0 的内容见下文，原样保留。

## 0.17.1 本版更新

- **修复：由 agent 启动 AutoCAD 时出现的许可崩溃弹窗或启动失败。**
  - `cad_start` 用 `DispatchEx` 启动 AutoCAD 时，DCOM 会把 MCP 服务端进程的环境传给 AutoCAD；这个环境又来自启动 MCP 服务端的 agent 宿主。
  - Codex（`shell_environment_policy inherit = "core"`）和使用官方 MCP SDK 默认环境的宿主，都会去掉 `ALLUSERSPROFILE` 等 Windows 登录变量。
  - 缺少 `ALLUSERSPROFILE` 时，Autodesk 许可代理 `AdskLicensingAgent.exe` 一启动就抛出 C++ 异常，每次重试都弹一个错误报告；在 MCP SDK 默认环境下，AutoCAD 甚至直接启动失败（COM 0x80080005 "服务器运行失败"）。
- **修复方式：** 启动 AutoCAD 前，从当前用户的默认登录环境按白名单补回缺失的 Windows 标准变量。已有的值不会被覆盖，白名单以外的变量也不会被复制，宿主特意去掉的密钥等变量仍然不会传给 AutoCAD。Skill 规定只能通过服务端的 `cad_start` 启动 AutoCAD，这是唯一的启动路径，所以对所有 agent 宿主都生效。
- **影响范围：** 只改变服务端新启动 AutoCAD 时的环境。附着已经运行的实例、离线 DXF 和其他工具都不受影响。在修复前由 agent 启动、目前仍在运行的 AutoCAD 实例，需要关闭后重新启动才能获得完整环境。

## 0.17.1 实际验证

- 全量回归 1006 项通过、18 项按环境跳过（Python 3.11 / uv）。新增三个测试：补变量逻辑的单元测试；Windows 上检查登录环境确实含这几个前置变量；以及真实启动路径测试，断言调用 `DispatchEx` 时 `ALLUSERSPROFILE` 已经存在。去掉修复后，最后这个测试会失败。
- 在本机 AutoCAD 2024 上，经真实 stdio MCP 服务端调用 `cad_start`，三种宿主环境各启动一个新实例，等待 45 秒后检查：

| 宿主环境 | 修复前 | 修复后 |
|---|---|---|
| MCP SDK 默认环境（通用 MCP 宿主） | AutoCAD 启动失败 | 启动成功，许可代理注册成功，错误报告弹窗 0 个，崩溃报告 0 个 |
| Codex `inherit=core` | 许可代理崩溃，连续弹出 3 个错误报告 | 启动成功，许可代理注册成功，错误报告弹窗 0 个，崩溃报告 0 个 |
| 完整环境（Claude Code 这类） | 正常 | 正常 |

- 根因取证：崩溃转储里的进程是 `AdskLicensingAgent.exe`，抛出的异常类型是 `std::runtime_error`。用 AutoCAD 进程的实际环境直接启动许可代理，可以稳定复现崩溃；只补回 `ALLUSERSPROFILE` 一个变量，崩溃就消失了。

---

以下为 0.17.0 发布说明，原样保留。

## 0.17.0 摘要

把 0.16.0 之后主分支上的行业标准与学习要点、原创示例图纸、安装器修复、Windows 后台审查稳定性修复，以及新增的活动 CAD 剖面填充和尺寸前缀能力，正式纳入 0.17.0。版本号同步到运行模块、pyproject、uv.lock、package.json、能力清单和首页。不声明任何客户工程图因此自动合格。

## 0.17.0 本版更新

- **活动 CAD 剖面填充**：`cad_mutate` 新增 `operation=hatch`，生成原生 HATCH。可以传已有闭合多段线或圆的 `boundary` 句柄，也可以传 `points`，由同一次写入在 `boundary_layer` 上画出闭合轮廓。可选 `inner` 句柄和 `inner_circles` 作孔岛。图案限 ANSI31、ANSI32、ANSI37、NET、SOLID。边界句柄在写入日志开始前校验，参数错误不会留下结果不明的写入。
- **尺寸**：`dimension` 新增 `rotation`（旋转尺寸）和 `text_override`。`text_override` 必须恰好含一个 `<>`，显示值保留实际测量，例如 `%%c<>`、`%%c<>×4.5`，不能用固定数字替代。
- **行业标准与学习要点**：标准索引从 50 条扩到 98 条，路线从 22 条扩到 24 条。新增环境设计、食品加工路线和六篇学习要点。六张原创示例图纸由路线返回，只作教学示例。
- **安装器**：`--force-reinstall` 生效，仓库身份规范化后精确比对，`--target` 参数修复。
- **稳定性**：Windows 上后台审查状态文件发生共享冲突时短暂重试。发布流程改为从包内读取版本号。

## 0.17.0 已有实际验证

- 全量回归 1003 项通过、18 项按环境跳过（Python 3.11 / uv）。功能分支在 Windows、Ubuntu 两个平台的 CI 均成功。
- 新增 `tests/test_cad_hatch_dimension.py`，覆盖填充、孔岛、点集轮廓、SOLID、错误输入不启动写入，以及 `text_override` 不能替换测量值。
- 在本机 AutoCAD 2024 上，通过真实 stdio MCP 写入了 ANSI31/ANSI37/SOLID 填充、圆形孔岛、旋转尺寸和 `%%c<>` 前缀尺寸，并查看了原生 WMF 预览。这只证明工具可用：同一次绘图任务的图纸没有通过用户验收，不能作为任何复绘质量的证据。
- 正式发布工作流在最终提交上，先通过双平台检查，再构建源码包与 WorkBuddy 包，执行隔离安装回归和 WorkBuddy 下载包检查，最后创建版本与附件。具体运行结果见 GitHub Actions。

## 使用范围

填充与尺寸前缀只是写入能力。剖面线方向与间距、尺寸摆放、视图比例都要按任务原图和标准另行确定。原图本身不按比例时，"按标注定尺"和"按原图比例描绘"是两种不同交付，开画前须与用户确认。行业索引和示例图纸是路由与教学资料，不代表已读全部标准正文，也不代表工程验收。

相关链接：[更新记录](../CHANGELOG.md)、[执行工具](execution-tools.md)、[使用说明](usage.md)、[GitHub Actions](https://github.com/luomufanye-cloud/luomu-cad/actions/workflows/checks.yml)、[0.16 验证记录](release-validation-0.16.md)。
