# Luomu CAD 0.17.0 发布说明与验证范围

日期：2026-11-25

摘要：把 0.16.0 之后主分支上的行业标准与学习要点、原创示例图纸、安装器修复、Windows 后台审查稳定性修复，以及新增的活动 CAD 剖面填充和尺寸前缀能力，正式纳入 0.17.0。版本号同步到运行模块、pyproject、uv.lock、package.json、能力清单和首页。不声明任何客户工程图因此自动合格。

## 本版更新

- **活动 CAD 剖面填充**：`cad_mutate` 新增 `operation=hatch`，生成原生 HATCH。可以传已有闭合多段线或圆的 `boundary` 句柄，也可以传 `points`，由同一次写入在 `boundary_layer` 上画出闭合轮廓。可选 `inner` 句柄和 `inner_circles` 作孔岛。图案限 ANSI31、ANSI32、ANSI37、NET、SOLID。边界句柄在写入日志开始前校验，参数错误不会留下结果不明的写入。
- **尺寸**：`dimension` 新增 `rotation`（旋转尺寸）和 `text_override`。`text_override` 必须恰好含一个 `<>`，显示值保留实际测量，例如 `%%c<>`、`%%c<>×4.5`，不能用固定数字替代。
- **行业标准与学习要点**：标准索引从 50 条扩到 98 条，路线从 22 条扩到 24 条。新增环境设计、食品加工路线和六篇学习要点。六张原创示例图纸由路线返回，只作教学示例。
- **安装器**：`--force-reinstall` 生效，仓库身份规范化后精确比对，`--target` 参数修复。
- **稳定性**：Windows 上后台审查状态文件发生共享冲突时短暂重试。发布流程改为从包内读取版本号。

## 已有实际验证

- 全量回归 1003 项通过、18 项按环境跳过（Python 3.11 / uv）。功能分支在 Windows、Ubuntu 两个平台的 CI 均成功。
- 新增 `tests/test_cad_hatch_dimension.py`，覆盖填充、孔岛、点集轮廓、SOLID、错误输入不启动写入，以及 `text_override` 不能替换测量值。
- 在本机 AutoCAD 2024 上，通过真实 stdio MCP 写入了 ANSI31/ANSI37/SOLID 填充、圆形孔岛、旋转尺寸和 `%%c<>` 前缀尺寸，并查看了原生 WMF 预览。这只证明工具可用：同一次绘图任务的图纸没有通过用户验收，不能作为任何复绘质量的证据。
- 正式发布工作流在最终提交上，先通过双平台检查，再构建源码包与 WorkBuddy 包，执行隔离安装回归和 WorkBuddy 下载包检查，最后创建版本与附件。具体运行结果见 GitHub Actions。

## 使用范围

填充与尺寸前缀只是写入能力。剖面线方向与间距、尺寸摆放、视图比例都要按任务原图和标准另行确定。原图本身不按比例时，"按标注定尺"和"按原图比例描绘"是两种不同交付，开画前须与用户确认。行业索引和示例图纸是路由与教学资料，不代表已读全部标准正文，也不代表工程验收。

相关链接：[更新记录](../CHANGELOG.md)、[执行工具](execution-tools.md)、[使用说明](usage.md)、[GitHub Actions](https://github.com/luomufanye-cloud/luomu-cad/actions/workflows/checks.yml)、[0.16 验证记录](release-validation-0.16.md)。
