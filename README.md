# Luomu CAD

日期：2026-11-06

摘要：由[luomufanye-cloud](https://github.com/luomufanye-cloud)编写并维护的通用CAD辅助Skill，供Agent进行图纸读取、参考复绘、离线DXF生成、局部修改、图纸检查及技术资料学习。当前为0.3.12实验版本，版本变化见[更新记录](CHANGELOG.md)。

## 作者与许可证

**作者与维护者：[luomufanye-cloud](https://github.com/luomufanye-cloud)。** 本项目自有源码、CAD业务规则、MCP适配器、Skill工作流及训练脚本由作者开发并维护，采用[MIT许可证](LICENSE)开源，版权署名为`Copyright (c) 2026 luomufanye-cloud`。

项目使用的第三方基础库在安装时作为依赖准备，各自遵循其许可证，见[依赖说明](DEPENDENCIES.md)。项目署名不改变这些依赖或所引用资料的权利归属。

## 功能

- [CAD参考图读取与核对](references/cad-source-intake.md)：读取图纸单位、嵌套图块和文字，核对构件的位置、方向，以及分段尺寸与总尺寸是否一致。
- 按明确的毫米参数生成直线墙体、门窗、中文房间标注、原生尺寸、门窗表、A3/A1模型空间图框及PNG预览。
- 在独立副本中修改指定门窗，刷新其宿主墙、尺寸和关联表格，核对其他对象的实体哈希；原文件保持不变。
- 回读DXF检查零长度、重复线、自交及尺寸覆盖，并实测生成门窗的宽度和开洞。
- [中文显示与尺寸界线](references/text-and-dimensions.md)：配置字体文件和字体族，检查中文映射与短界线参数；保留真实测量，按目标比例控制留白，并在目标CAD查看原生显示。
- 参考复绘按[忠实复绘流程](references/faithful-redraw.md)核对原生尺寸、显示文字、声明的样式/文字位置及内容清单；局改按基线哈希检测范围外变化和额外新增，保护前轮修正。
- 根据给定的房间范围、家具尺寸和通行净距，辅助计算矩形家具布局，并避开指定的出入口及通道；支持的形状和计算条件见[布局工具说明](references/learned/layout-geometry-capability-gates.md)。
- 通过Scrapling解析公开资料，记录来源、时间、图注与文档链接，去重、检索并蒸馏经审阅的工作方法。
- 提供节点构造、施工工序、材料参数和专业系统的技术资料与练习，支持工序顺序、参数适用条件和端子连接检查，见[专业主题与验证范围](references/professional-learning.md)。
- Windows下通过本项目MCP服务端附着已运行的AutoCAD，读取文档和实体；写入需显式会话开关、文档身份及操作ID。

## 安装到Agent

使用完整仓库安装通用Skill，按Agent宿主的能力选择资料阅读、离线制图或MCP工具调用。参考阅读无需安装依赖；`python scripts/preflight.py`检查环境，`python scripts/verify_tasks.py`验证可复现的文件与知识卡任务。安装步骤和运行条件如下。

本仓库支持作为文件夹形式的Skill安装。Agent需要能读取Skill文件、执行本机命令，并允许启动子进程。不同宿主的Skill目录、刷新方式和MCP配置格式各有区别，安装Skill不会自动为所有宿主注册MCP。

1. 下载[完整仓库ZIP](https://github.com/luomufanye-cloud/luomu-cad/archive/refs/heads/main.zip)并解压，或克隆整个仓库。将包含SKILL.md的根目录命名为`luomu-cad`，放入Agent宿主指定的Skill目录；不要再额外嵌套一层同名目录。
2. 保留完整仓库，尤其是SKILL.md、scripts、src、references、examples、pyproject.toml和uv.lock。只复制SKILL.md或只安装Python包，不能替代完整Skill安装。
3. 按宿主要求刷新或重新加载Skill，让Agent读取SKILL.md，然后运行下面的一条安装验收命令。
4. 需要在宿主中直接调用工具或操作活动AutoCAD时，再按[MCP接入说明](references/usage.md)配置随包服务。

运行条件：

| 项目 | 条件 |
| --- | --- |
| 自动初始化入口 | Windows x86_64、PowerShell，以及可写入的技能目录；环境和结果写入本目录下的.venv、runtime、outputs |
| 首次依赖准备 | 能访问所需包源和官方运行时下载地址。脚本使用uv准备独立Python 3.11环境；找不到uv时包含下载并校验官方uv的分支 |
| Agent权限 | 能执行本机命令和启动stdio MCP子进程；仅能阅读文件的Agent可以查看方法与知识卡，不能运行绘图工具 |
| 离线DXF、几何检查与知识卡 | 无需安装AutoCAD；公开资料采集另外需要网络，并受来源访问条件约束 |
| 活动AutoCAD | Windows上已安装且正在运行的、可通过ActiveX访问的AutoCAD；还需MCP会话及对应操作授权 |

基础离线功能也可在Python 3.11/3.12的其他系统上使用uv运行；run.ps1自动入口面向Windows，其他系统与各宿主的完整安装流程尚未逐一验收。

可以把这段话交给Agent：

> 将 https://github.com/luomufanye-cloud/luomu-cad 安装为luomu-cad Skill，保留完整仓库。读取SKILL.md，运行scripts/run.ps1 -Action verify，检查最终ok=true和进程退出码0，报告实际输出位置。需要宿主MCP时合并生成的runtime/mcp-config.json服务条目；需要操作AutoCAD时再核对references/usage.md的连接与授权条件。

## 一条命令验收安装

在技能根目录运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action verify
```

该命令先准备独立环境，再经真实stdio MCP完成服务检查和示例出图，重新读取生成的DXF、核对几何和产物哈希，并检查PNG是否有效。它不连接或修改AutoCAD；相同软件版本和输入重复执行时复用经过哈希核验的自检产物，不重复叠画。

成功应同时满足：进程退出码0、最终JSON的ok=true、checks中的artifact_hashes/dxf_readback/preview_file均为PASS。报告位于runtime/verification/installation.json，示例结果位于返回的artifacts路径。图面人工检查和专业审核仍分别标记，不由安装验收自动判为通过。

命令还会生成当前电脑的runtime/mcp-config.json，包含绝对路径及默认关闭活动CAD写入的环境设置。使用mcpServers JSON格式的宿主可合并其中的luomu-cad条目；其他宿主取其中command、args、env按其格式填写。保留宿主原有其他服务，勿整份覆盖已有配置。配置含本机路径，应留在本地。

从其他目录运行时，把-File后面的脚本换成完整路径即可；-Action generate的相对Spec路径按技能根目录解释，外部项目输入使用绝对路径。

## 首次自检与离线示例

在包含SKILL.md的技能根目录打开PowerShell，依次运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action generate -Spec .\examples\two-room.json -Job demo-001
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action research -ResearchAction status
```

health成功时应返回ok=true、transport=stdio-mcp，以及当前安装目录下的output_root；它不会连接AutoCAD。generate成功后，outputs/demo-001下应有plan.dxf、preview.png、spec.json、qa.json和manifest.json，结果中的几何检查应为PASS。图面仍需查看，专业设计仍需对应审核，不能只凭文件存在认定交付通过。

重复生成同一job和输入时只返回已提交结果；同名不同参数拒绝执行。示例尺寸均为示范设计采用值，不能当作现场实测。相对Spec路径按技能根目录解释，外部项目输入使用绝对路径。

不支持在界面中配置MCP、但允许执行本机命令的Agent，可以通过scripts/entry.py使用随包真实stdio MCP完成离线工作。CLI单次call默认只读；活动CAD连续读写需要持久MCP会话，不能绕过服务直连COM。配置模板和写入条件见[使用说明](references/usage.md)。

## 范围与来源

项目中的墙体与开洞生成、任务事务、局部编辑、MCP服务和AutoCAD桥由本项目实现；仓库不分发其他CAD服务项目的源码、模板或原生插件。公开资料研究、检查及求解模块延续本项目作者此前维护的代码。基础库作为外部依赖安装，各自许可证见[依赖与资料说明](DEPENDENCIES.md)。

首版支持中心轴直线墙、同一墙段内的门窗、闭合外墙包围的房间和矩形排布。曲墙、任意图片精确复绘、三维BIM、原生插件、DWG/PDF出图及全专业规范审查不属于已实现范围。图纸资料分类来自文字和图注，不能当作逐图验收；国外案例参数不自动进入项目输入。

默认不修改活动CAD，不启动/重启应用，不切换活动文档，不取消用户命令，也没有原始LISP、任意命令或桌面控制入口。AutoCAD实际读写受运行环境影响；测试使用的模拟对象只证明接口保护，不代表所有AutoCAD版本已实机验证。

0.2.1增加[墙地防水连续性原理训练](references/waterproof-training-2026-11-04.md)：生成并回读原生DXF示意，识别断点与缺失上翻。它使用无工程单位的任意坐标，不构成施工节点设计。

## 安装支持与故障排查

支持入口：[提交安装或使用问题](https://github.com/luomufanye-cloud/luomu-cad/issues/new)。先运行-Action verify并保留实际错误；自检失败时会返回非零退出码，不能只看到依赖安装完成就认定Skill可用。

| 现象 | 检查方法 |
| --- | --- |
| Agent找不到Skill | 检查宿主指定目录、是否多嵌套了一层文件夹，以及是否按宿主要求刷新；Skill目录根部应能直接看到SKILL.md |
| uv、Python或包下载失败 | 检查对应官方地址和包源是否可访问、技能目录是否可写；依赖准备阶段失败可能尚无JSON报告，需保留终端错误，不绕过校验 |
| 自检通过，宿主里仍没有工具 | 检查是否合并MCP服务条目、路径是否对应当前电脑、宿主是否要求另一种配置格式，以及工具列表是否已刷新 |
| 自检文件被修改后失败 | 保留现有产物和报告，用新的完整下载副本复核；不要覆盖其他工作文件或手工改报告冒充通过 |
| 活动AutoCAD连接失败 | 离线自检与CAD附着分别处理；检查AutoCAD是否已运行、版本、用户会话及权限，并参考[MCP使用说明](references/usage.md) |

反馈请提供软件版本、Windows版本、Agent宿主及版本、完整执行命令、最终错误和必要日志。日志中的个人路径、客户信息或凭据先脱敏，私人图纸无需作为默认附件。项目支持按下述已验证路径说明，不承诺未验收的所有Agent和CAD版本具有相同表现。

## 开发与验证

0.3.0新增[风盘安装与计算训练](references/fan-coil-training-2026-11-04.md)：依据选定厂家手册进行毫米吊杆定位、冷凝水提升/坡度/空间错误题与换型号题，并完成给定水侧换热率的流量、流速、普通阀阻、给定阻力扬程及温差变化练习。脚本和训练场景为本项目自行编写，原PDF和图页不随包分发；两项技术卡仅在明确练习范围内达到exercise_checked。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\train_fan_coil.py
```

图纸、预览与逐项结果写入runtime/training/fan-coil-installation。参数出处、自拟训练输入、完整演算与尚未覆盖的能力均在对应记录中列明，不把运行脚本等同工程项目验收。

截至2026-11-05，0.3.1的安装验证范围如下：

| 检查 | 结果与边界 |
| --- | --- |
| 首次准备分支 | 已实测官方uv下载、校验、解压与依赖准备；在PATH无uv/Python、无.venv且包含空格/中文路径的新目录完成verify。完整验收使用已校验的uv安装包及Python/包缓存 |
| 一条命令安装验收 | 经真实stdio MCP生成DXF、PNG及检查文件，独立回读几何和检查哈希/PNG通过；未操作AutoCAD |
| 生成的MCP配置 | 已从安装目录之外的工作目录实际启动服务、列出工具并核对当前目录和默认只读设置；不是各Agent界面注册验收 |
| 软件回归与发布包 | 安装回归覆盖正常结果、产物变动、跨目录借用、错误环境根目录、错误DXF单位和损坏PNG；scripts/release_smoke.py对实际源码ZIP执行独立环境全量测试与安装验收 |
| 尚未逐一验证 | 完全无Python/包缓存的所有网络环境、各个Agent宿主的Skill自动发现和界面注册、其他电脑/各版本AutoCAD的实机读写 |
| GitHub在线CI | 当前工作流文件尚未上传成功，未声称GitHub Actions已通过；上述结果来自本地独立环境 |

这些证据支持“满足条件后可运行离线功能”，不支持“任意Agent下载后零配置完成全部CAD操作”。原始验证日志与生成产物保留在维护者的私有runtime目录，不随公开仓库分发。

此前已验证离线出图、门窗局改及中文样图。0.2.0新增技术知识卡和限定练习，首批为厨卫防水及接地系统，见[实际技术学习记录](references/technical-study-2026-11-04.md)。0.1.1从实际原文与三张图中新增两条方法，并增加四个布局回归用例和真实MCP拒绝检查，见[学习与应用记录](references/learning-review-2026-11-04.md)。

```powershell
uv sync --python 3.11 --extra dev --no-editable
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_release.py
```

发布包只包含源码、示例参数与必要参考；不包括本机图纸、采集数据库、预览缓存、登录数据、环境变量或历史日志。MIT许可仅覆盖本项目代码，不授予第三方资料的再分发权。

## 相关链接

[Skill入口](SKILL.md) · [MCP与使用范围](references/usage.md) · [资料研究](references/drawing-research.md) · [依赖](DEPENDENCIES.md) · [许可证](LICENSE)
