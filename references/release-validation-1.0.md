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
- 实机验证使用 Windows x86_64 和 AutoCAD 2024（24.3），基于提交 `e80a36f`。两条 stdio 会话启动并绑定了不同的 AutoCAD PID 和 HWND，并确认各自的空白图纸 token。
- 两条会话并发执行原生 CAD 写入。原生回读分别得到 12 条直线和 12 个圆，句柄与各自的写入回执逐项一致。跨文档 token 查询返回 `DOCUMENT_TOKEN_MISMATCH`。两条服务实际执行 `mutate` 的时间区间有 21 对重叠，单对最长约 125 毫秒。
- 实测覆盖对象类别、句柄和数量。通用回读在本环境未返回直线端点或圆心及半径，因此几何坐标未验收。测试图保留在各自的 AutoCAD 窗口中，未另存。
- 每条专用 MCP 会话须保持连接。实机初轮断开两条会话后，普通 ActiveX 重新附着只找到了一个实例。

## 相关链接

- [多窗口配置与操作](cad-task-coordination.md#不同-autocad-实例并行)
- [能力清单](../capabilities.yaml)
- [更新记录](../CHANGELOG.md)
- [AutoCAD ActiveX 应用连接](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX/files/GUID-73EC319D-9D7D-43FF-91B7-78CF36284028.htm)
