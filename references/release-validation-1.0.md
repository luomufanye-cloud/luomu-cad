# Luomu CAD 1.0.0 发布说明与验证范围

日期 2026-11-25

摘要：通过独立的 MCP 服务在同一台 Windows 电脑上运行多个 AutoCAD 任务。每条专用会话显式启动并验证自己的 AutoCAD 进程，绑定实际窗口，并保留独立操作日志。

## 本版更新

- 一个 Agent 可使用两条专用 MCP 服务。多个 Agent 可分别使用各自的服务。
- 每个实际 AutoCAD 窗口有独立任务锁。同一进程中的图纸标签由该进程共用一把锁。
- 启动通过进程 ID 和 HWND 核对实例身份。连接后使用该实例下的图纸 token 读写。

## 验证范围

- Windows 下通过 CAD、安装和接口回归，覆盖独立进程启动判定、窗口锁冲突与释放、同窗口写入互斥、不同窗口的任务重叠、实例身份变化和跨窗口 token 拒绝。
- 两个真实 stdio MCP 服务分别加载 `left` 和 `right` 配置，验证了 1.0.0 版本、同时持有各自启动前的占用、写入开关和任务释放。
- 双窗口原生绘制仍待在已授权的 Windows AutoCAD 环境验证。当前多实例能力在[能力清单](../capabilities.yaml)中为 `pilot`。

## 相关链接

- [多窗口配置与操作](cad-task-coordination.md#不同-autocad-实例并行)
- [能力清单](../capabilities.yaml)
- [更新记录](../CHANGELOG.md)
- [AutoCAD ActiveX 应用连接](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX/files/GUID-73EC319D-9D7D-43FF-91B7-78CF36284028.htm)
