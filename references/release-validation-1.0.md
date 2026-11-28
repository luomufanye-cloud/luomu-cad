# Luomu CAD 1.0.0 发布说明与验证范围

日期 2026-11-27

摘要：1.0.0 支持同机多个 AutoCAD 进程并行。离线改图默认写回原件，PDF 和另存按明确请求生成。

## 安装

同一个通用包可放入支持 Agent Skills 的宿主技能目录，或在支持本地 stdio MCP 的宿主注册工具。能运行命令的 Agent 也可以通过随包 CLI 完成离线任务。活动 AutoCAD 需要本机 Windows 和持久 MCP 会话。[下载通用包](https://github.com/luomufanye-cloud/luomu-cad/releases/download/v1.0.0/luomu-cad-1.0.0-source.zip) · [多宿主接入](https://github.com/luomufanye-cloud/luomu-cad/blob/main/references/usage.md)

## 本版更新

- 一个 Agent 可使用两条专用 MCP 服务。多个 Agent 可分别使用各自的服务。
- 每个实际 AutoCAD 窗口有独立任务锁。同一进程中的图纸标签由该进程共用一把锁。
- 启动通过进程 ID 和 HWND 核对实例身份。连接后使用该实例下的图纸 token 读写。新进程会补齐缺失的 Windows 登录变量，继承 0.17.1 对许可代理崩溃的修复。
- 门窗局改和共享图册先校核暂存成果，再更新原路径的图纸与回执。文件替换失败会回滚，进程中断留下恢复记录并阻止读取不完整的版本。下次写入先恢复原件。图册累计标记尚未刷新的旧 PDF 和移除的图页。

## 从 0.17.1 升级

| 需求 | 调用参数 |
| --- | --- |
| 单独从 DXF 导出 PDF | `workbench_export_pdf` 传 `explicit_request=true` |
| 共享图册生成单页 PDF 和合册 | `workbench_project` 传 `export_pdf=true`，CLI 使用 `--export-pdf` |
| 局改输出独立副本 | `workbench_patch_opening` 传 `new_copy=true` |
| 活动图另存至新 DWG | `cad_save_as` 传 `explicit_request=true` |

## 活动 AutoCAD

- Windows x86_64 上，两条真实 stdio MCP 服务分别在 MCP SDK 默认环境、精简 Windows 环境下启动 AutoCAD 2024（24.3）。启动前两种服务环境均缺少 `ALLUSERSPROFILE`。两条会话确认了各自的 PID、HWND 和空白图纸 token。启动后第 45 秒未发现新增 Autodesk 错误报告进程。
- 两条会话分别写入 12 条直线和 12 个圆。每个句柄都与写入回执一致，`cad_native_entity_data` 回读的线段端点、圆心和半径逐项匹配。跨窗口查询返回 `DOCUMENT_TOKEN_MISMATCH`，未显式请求的另存返回 `EXPLICIT_NEW_FILE_REQUEST_REQUIRED`，目标路径无 DWG。
- 本次有 23 对 stdio 客户端写入调用时间重叠。此前提交 `e80a36f` 的实机测试在服务端采集到 21 对实际写入时间重叠。测试图存于各自的活动窗口，未写入磁盘。
- 专用服务保持连接以保留实例绑定。早期一次断开两条服务后的普通 ActiveX 重新附着仅找到一个实例。实机范围为上述 Windows 与 AutoCAD 版本上的测试图形。

## 离线与安装

- 回归覆盖旧版带 PDF 的图册、默认只输出 DXF、明确请求时输出 PDF、连续修订与过期版本拒绝、暂存独立尺寸不通过、替换失败回滚及中断后恢复重试。适用用例见[开口改图测试](https://github.com/luomufanye-cloud/luomu-cad/blob/v1.0.0/tests/test_drawing.py)和[图册测试](https://github.com/luomufanye-cloud/luomu-cad/blob/v1.0.0/tests/test_shared_project.py)。
- 通用源码包经过 Windows 和 Ubuntu 软件检查、解压安装和 DXF 回读检查。客户图纸的工程及交付验收仍按各任务的原始要求进行。

## 相关链接

- [多窗口配置与操作](cad-task-coordination.md#不同-autocad-实例并行)
- [原地修订与图册](shared-project-atlas.md)
- [0.17.1 启动修复记录](release-validation-0.17.md)
- [贡献与验证方法](../CONTRIBUTING.md)
- [能力清单](../capabilities.yaml)
- [更新记录](../CHANGELOG.md)
- [GitHub Actions](https://github.com/luomufanye-cloud/luomu-cad/actions/workflows/checks.yml)
- [AutoCAD ActiveX 应用连接](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX/files/GUID-73EC319D-9D7D-43FF-91B7-78CF36284028.htm)
