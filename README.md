# Luomu CAD

日期：2026-11-04

摘要：由[luomufanye-cloud](https://github.com/luomufanye-cloud)维护的CAD自动化项目，提供MCP服务、参数化建筑DXF、局部修改、几何检查、矩形布局求解和公开图纸资料研究。当前为0.3.0实验版本。

## 功能

- 按明确的毫米参数生成直线墙体、门窗、中文房间标注、原生尺寸、门窗表、A3/A1模型空间图框及PNG预览。
- 在独立副本中修改指定门窗，刷新其宿主墙、尺寸和关联表格，核对其他对象的实体哈希；原文件保持不变。
- 回读DXF检查零长度、重复线、自交及尺寸覆盖，并实测生成门窗的宽度和开洞。
- 用调用方给定的净距求解轴对齐矩形家具布局；结果不等于规范认证。
- 不规则边界、任意旋转或未映射的约束明确拒绝，不通过忽略输入来返回成功。已确认的矩形入口保留区可显式表示为障碍。
- 通过Scrapling解析公开资料，记录来源、时间、图注与文档链接，去重、检索并蒸馏经审阅的工作方法。
- 以技术知识卡学习节点构造、施工工序、材料参数与专业系统；支持工序、参数适用性及指定端子图练习，按[接单能力矩阵](references/professional-learning.md)补齐主题。
- Windows下通过本项目MCP服务端附着已运行的AutoCAD，读取文档和实体；写入需显式会话开关、文档身份及操作ID。

## 安装到Agent

本仓库支持作为文件夹形式的Skill安装。Agent需要能读取Skill文件、执行本机命令，并允许启动子进程。不同宿主的Skill目录、刷新方式和MCP配置格式各有区别，安装Skill不会自动为所有宿主注册MCP。

1. 下载仓库ZIP并解压，或克隆整个仓库。将包含SKILL.md的根目录命名为`luomu-cad`，放入Agent宿主指定的Skill目录；不要再额外嵌套一层同名目录。
2. 保留完整仓库，尤其是SKILL.md、scripts、src、references、examples、pyproject.toml和uv.lock。只复制SKILL.md或只安装Python包，不能替代完整Skill安装。
3. 按宿主要求刷新或重新加载Skill，让Agent读取SKILL.md，然后先完成下面的自检和离线示例。
4. 需要在宿主中直接调用工具或操作活动AutoCAD时，再按[MCP接入说明](references/usage.md)配置随包服务。

运行条件：

| 项目 | 条件 |
| --- | --- |
| 自动初始化入口 | 64位Windows、PowerShell，以及可写入的技能目录；环境和结果写入本目录下的.venv、runtime、outputs |
| 首次依赖准备 | 能访问所需包源和官方运行时下载地址。脚本使用uv准备独立Python 3.11环境；找不到uv时包含下载并校验官方uv的分支 |
| Agent权限 | 能执行本机命令和启动stdio MCP子进程；仅能阅读文件的Agent可以查看方法与知识卡，不能运行绘图工具 |
| 离线DXF、几何检查与知识卡 | 无需安装AutoCAD；公开资料采集另外需要网络，并受来源访问条件约束 |
| 活动AutoCAD | Windows上已安装且正在运行的、可通过ActiveX访问的AutoCAD；还需MCP会话及对应操作授权 |

基础离线功能也可在Python 3.11/3.12的其他系统上使用uv运行；run.ps1自动入口面向Windows，其他系统与各宿主的完整安装流程尚未逐一验收。

可以把这段话交给Agent：

> 将 https://github.com/luomufanye-cloud/luomu-cad 安装为luomu-cad Skill，保留完整仓库。先读取SKILL.md，在技能根目录运行scripts/run.ps1 -Action health，再用examples/two-room.json验证离线出图。报告真实结果和输出位置；需要操作AutoCAD时，按references/usage.md接入随包MCP。

## 首次自检与离线示例

在包含SKILL.md的技能根目录打开PowerShell，依次运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action generate -Spec .\examples\two-room.json -Job demo-001
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action research -ResearchAction status
```

health成功时应返回ok=true、transport=stdio-mcp，以及当前安装目录下的output_root；它不会连接AutoCAD。generate成功后，outputs/demo-001下应有plan.dxf、preview.png、spec.json、qa.json和manifest.json，结果中的几何检查应为PASS。图面仍需查看，专业设计仍需对应审核，不能只凭文件存在认定交付通过。

重复生成同一job和输入时只返回已提交结果；同名不同参数拒绝执行。示例尺寸均为示范设计采用值，不能当作现场实测。若从其他工作目录调用脚本，脚本路径和Spec路径都使用绝对路径。

不支持在界面中配置MCP、但允许执行本机命令的Agent，可以通过scripts/entry.py使用随包真实stdio MCP完成离线工作。CLI单次call默认只读；活动CAD连续读写需要持久MCP会话，不能绕过服务直连COM。配置模板和写入条件见[使用说明](references/usage.md)。

## 范围与来源

项目中的墙体与开洞生成、任务事务、局部编辑、MCP服务和AutoCAD桥由本项目实现；仓库不分发其他CAD服务项目的源码、模板或原生插件。公开资料研究、检查及求解模块延续本项目作者此前维护的代码。基础库作为外部依赖安装，各自许可证见[依赖与资料说明](DEPENDENCIES.md)。

首版支持中心轴直线墙、同一墙段内的门窗、闭合外墙包围的房间和矩形排布。曲墙、任意图片精确复绘、三维BIM、原生插件、DWG/PDF出图及全专业规范审查不属于已实现范围。图纸资料分类来自文字和图注，不能当作逐图验收；国外案例参数不自动进入项目输入。

默认不修改活动CAD，不启动/重启应用，不切换活动文档，不取消用户命令，也没有原始LISP、任意命令或桌面控制入口。AutoCAD实际读写受运行环境影响；测试使用的模拟对象只证明接口保护，不代表所有AutoCAD版本已实机验证。

0.2.1增加[墙地防水连续性原理训练](references/waterproof-training-2026-11-04.md)：生成并回读原生DXF示意，识别断点与缺失上翻。它使用无工程单位的任意坐标，不构成施工节点设计。

## 开发与验证

0.3.0新增[风盘安装与计算训练](references/fan-coil-training-2026-11-04.md)：依据选定厂家手册进行毫米吊杆定位、冷凝水提升/坡度/空间错误题与换型号题，并完成给定水侧换热率的流量、流速、普通阀阻、给定阻力扬程及温差变化练习。脚本和训练场景为本项目自行编写，原PDF和图页不随包分发；两项技术卡仅在明确练习范围内达到exercise_checked。

```powershell
.\.venv\Scripts\python.exe -X utf8 scripts\train_fan_coil.py
```

图纸、预览与逐项结果写入runtime/training/fan-coil-installation。参数出处、自拟训练输入、完整演算与尚未覆盖的能力均在对应记录中列明，不把运行脚本等同工程项目验收。

截至2026-11-04，0.2.2的实际验证范围如下：

| 检查 | 结果与边界 |
| --- | --- |
| 公开仓库独立下载副本 | 从没有.venv和runtime的状态开始，run.ps1成功准备独立环境、安装56个依赖并通过真实stdio MCP自检；本次使用已有uv及Python/包缓存 |
| 下载副本离线示例 | 生成DXF、PNG及检查文件，几何检查PASS，并核对产物哈希；本次未操作AutoCAD |
| 源码包程序测试 | 实际源码ZIP在独立虚拟环境中62项通过；属于软件及限定练习检查，不是工程能力或全专业规范验收 |
| 尚未逐一验证 | 无既有uv/缓存的下载分支、各个Agent宿主的Skill自动发现和MCP注册、其他电脑/各版本AutoCAD的实机读写 |
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
