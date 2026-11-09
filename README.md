# Luomu CAD

让 Agent 读取参考图、绘制 CAD、修改图纸并检查交付文件。

**作者与维护者：[luomufanye-cloud](https://github.com/luomufanye-cloud)** · **版本：0.15.0** · [MIT 许可证](LICENSE)

日期：2026-11-09

摘要：Luomu CAD 是一套 CAD 辅助 Skill 和 MCP 工具。把参考资料与要求交给 Agent，由它选择绘图工具、完成修改，再结合原图、文件回读和独立子代理检查结果。支持离线 DXF、PDF 输出，以及本地 AutoCAD 中的 DWG 操作。

## 可以做什么

| 任务 | 功能与入口 |
| --- | --- |
| 参考图复绘 | 图片识读、矢量 PDF 源对象提取、源清单构建及原图对照，见[参考复绘](references/faithful-redraw.md) |
| 墙体、门窗和家具 | 参数化构件、墙体切洞、门扇开向、组件位置及原生几何检查，见[构件库](references/house-plan-components.md) |
| 局部改图 | 从最新文件建立修订副本，修改指定对象，核对关联尺寸及范围外实体，见[修改流程](references/model-workflow.md) |
| 房间和柜体多视图 | 共享尺寸生成房间平面、完成面、墙面立面、定向剖面和 PDF 图册；柜体支持平面、正立面及侧剖，见[房间图册](references/shared-project-atlas.md)与[柜体多视图](references/casework-multiview.md) |
| 文件输出 | 固定纸张和比例的矢量 PDF；通过 CAD MCP 另存 DWG、关闭重开及回读，见[执行工具](references/execution-tools.md) |
| 分专业检查 | 28 类行业、103 种图种的任务分类与标准选路，配合 13 类专业配置开展几何、标注和样式检查，见[行业索引](references/industry-delivery-index.md)与[专业配置](references/professional-cad.md) |
| 独立交付复核 | 默认配备 `luomu-cad-reviewer`，核对客户原始要求、源图、实际文件和逐项证据，见[客户交付](references/customer-delivery.md) |
| 三维与技术资料 | 参数化实体、STEP 回读、IFC 构件关系、服装纸样及施工节点练习，见[计算内核](references/cad-engine-usage.md)、[实体验收](references/solid-model-review.md)及[技术卡](references/technical/index.md) |

参考复绘保留源图的对象、尺寸和设计；开放设计按已确认的任务书展开。图纸采用本项目选定的地区、专业、阶段和标准条文，具体检查项随任务建立。行业分类用于选择工作流和检查清单，各项执行结果记录在对应图纸的报告中。

## 安装 Skill

1. 下载[完整仓库 ZIP](https://github.com/luomufanye-cloud/luomu-cad/archive/refs/heads/main.zip)，或克隆本仓库。
2. 将根目录命名为 `luomu-cad`，放进 Agent 宿主指定的 Skill 目录。目录根部应直接包含 `SKILL.md`、`scripts`、`src`、`references`、`examples`、`pyproject.toml` 和 `uv.lock`。
3. 按宿主要求刷新 Skill，让 Agent 读取 `SKILL.md`。
4. 在 Skill 根目录运行安装检查：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action verify
```

Windows 自动入口要求 x86_64、PowerShell、可写的 Skill 目录，以及首次准备依赖所需的网络。脚本通过 uv 准备独立 Python 3.11 环境，生成示例 DXF、PNG 和检查报告。

安装成功时，进程退出码为 `0`，最终 JSON 的 `ok=true`，`artifact_hashes`、`dxf_readback`、`preview_file` 均为 `PASS`。报告位于 `runtime/verification/installation.json`，示例文件位置由 `artifacts` 返回。

也可以把下面这段交给 Agent：

> 将 https://github.com/luomufanye-cloud/luomu-cad 的完整仓库安装为 luomu-cad Skill。读取 SKILL.md，运行 scripts/run.ps1 -Action verify，检查退出码、最终结果和产物位置。需要宿主 MCP 时，按该宿主的配置格式合并 runtime/mcp-config.json 中的服务参数；需要操作 AutoCAD 时，再按 references/usage.md 建立活动 CAD 会话。

## 接入 MCP 和 AutoCAD

安装检查会生成 `runtime/mcp-config.json`，其中包含当前电脑的服务路径、参数和默认只读设置。使用 `mcpServers` JSON 的宿主可合并 `luomu-cad` 条目；其他宿主按各自格式填写相同的 `command`、`args` 和 `env`，保留已有服务。

| 使用方式 | 环境与步骤 |
| --- | --- |
| 阅读资料与技术卡 | Agent 可读取完整 Skill 文件夹 |
| 离线 DXF 和 PDF | Python 3.11/3.12、锁定依赖及子进程执行权限；文件任务由随包 stdio MCP 执行 |
| 活动 AutoCAD / DWG | 同一 Windows 环境中已安装且运行的 AutoCAD、可用 CAD MCP 及任务授权；写入时启用服务端开关，携带文档 token 和操作 ID |
| 独立验收子代理 | 安装检查配置项目级角色，宿主加载后执行独立审核；其他客户项目可用 `-AgentProjectRoot` 指定目录，见[安装与调用](references/reviewer-installation.md) |
| 其他系统 | 基础离线功能通过 uv 和 Python 运行，按[使用说明](references/usage.md)准备环境 |

首次连接先检查 MCP 服务，再列出 CAD 文档、连接目标图纸并读取实体。确认文档正确后执行获授权的修改。实际配置、接口参数和连接恢复步骤见 [MCP 使用说明](references/usage.md)。

## 跑一个示例

在 Skill 根目录依次运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action generate -Spec .\examples\two-room.json -Job demo-001
```

`health` 检查离线服务，返回 `ok=true`、`transport=stdio-mcp` 和当前目录的 `output_root`。`generate` 在 `outputs/demo-001` 输出 `plan.dxf`、`preview.png`、`spec.json`、`qa.json` 和 `manifest.json`。这两步使用离线文件流程，活动 AutoCAD 连接按上一节单独建立。

示例采用演示尺寸。实际任务填写已确认的尺寸与来源；相同 job 和输入复用已核验产物，输入变化时使用新 job。相对 Spec 路径以 Skill 根目录为基准，外部项目输入使用绝对路径。

## 从需求到交付

1. **确认需求**：登记原始资料、图种、修改范围、单位、尺寸依据、交付格式和版本。
2. **选择流程**：按专业选择标准与检查项，参考复绘建立源对象清单，局部修改采用最新基线。
3. **绘制与修改**：使用对应工具，保存修订文件，核对受影响的对象、标注和跨图关系。
4. **独立复核**：交给 `luomu-cad-reviewer` 查看原始要求、源图和实际文件；逐项处理发现的问题。
5. **检查文件**：回读原生实体与尺寸，查看整图和局部，核对 PDF 的纸张、比例、字体及线重；DWG 按任务完成保存与重开检查。

安装检查记录运行环境，软件测试记录接口行为，交付报告记录本次图纸逐项验收。工程项目另按对应专业要求完成计算、审查和签署。使用步骤见[忠实复绘](references/faithful-redraw.md)、[标准依据](references/standards-foundation.md)和[客户交付](references/customer-delivery.md)。

## 常见问题

| 现象 | 处理方法 |
| --- | --- |
| Agent 找不到 Skill | 检查宿主目录、文件夹层级和刷新方式，确认根目录有 `SKILL.md` |
| uv、Python 或包下载失败 | 检查终端原始错误、官方地址与包源访问、目录写权限 |
| 自检通过，宿主工具列表没有更新 | 核对服务路径和宿主配置格式，再按宿主要求重新加载 MCP |
| 活动 AutoCAD 连接失败 | 检查已运行版本、用户会话、进程权限和 MCP 返回错误，按[连接说明](references/usage.md)恢复 |
| 字体、尺寸或线条显示异常 | 参照[文字与尺寸](references/text-and-dimensions.md)、[PDF 表现](references/pdf-presentation.md)核对源字体、实体属性和输出比例 |

需要帮助时可[提交 Issue](https://github.com/luomufanye-cloud/luomu-cad/issues/new)，附上版本、操作步骤、最终错误及必要的脱敏日志。

## 开发与验证

```powershell
uv sync --python 3.11 --extra dev --no-editable
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_release.py
```

版本测试、实际样例和运行条件见[0.15 验证记录](references/release-validation-0.15.md)、[原生 CAD 检查](references/native-validation.md)及 [GitHub Actions](https://github.com/luomufanye-cloud/luomu-cad/actions/workflows/checks.yml)。

## 作者与许可

Luomu CAD 的项目代码、参数化构件、CAD 业务规则、MCP 适配器与 Skill 工作流由 **luomufanye-cloud** 开发维护，采用 [MIT 许可证](LICENSE)。版权署名：`Copyright (c) 2026 luomufanye-cloud`。

安装依赖、可选计算内核及参考资料的来源与许可集中在[依赖说明](DEPENDENCIES.md)和[第三方声明](THIRD_PARTY_NOTICES.md)。发布包包含项目源码、示例和必要参考；本机运行环境、客户图纸与私有日志保存在本地。

## 相关链接

[Skill 入口](SKILL.md) · [安装与 MCP](references/usage.md) · [行业索引](references/industry-delivery-index.md) · [更新记录](CHANGELOG.md) · [问题反馈](https://github.com/luomufanye-cloud/luomu-cad/issues)
