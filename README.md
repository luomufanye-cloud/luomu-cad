# Luomu CAD

日期：2026-11-04

摘要：由[luomufanye-cloud](https://github.com/luomufanye-cloud)维护的CAD自动化项目，提供MCP服务、参数化建筑DXF、局部修改、几何检查、矩形布局求解和公开图纸资料研究。当前为0.2.2实验版本。

## 功能

- 按明确的毫米参数生成直线墙体、门窗、中文房间标注、原生尺寸、门窗表、A3/A1模型空间图框及PNG预览。
- 在独立副本中修改指定门窗，刷新其宿主墙、尺寸和关联表格，核对其他对象的实体哈希；原文件保持不变。
- 回读DXF检查零长度、重复线、自交及尺寸覆盖，并实测生成门窗的宽度和开洞。
- 用调用方给定的净距求解轴对齐矩形家具布局；结果不等于规范认证。
- 不规则边界、任意旋转或未映射的约束明确拒绝，不通过忽略输入来返回成功。已确认的矩形入口保留区可显式表示为障碍。
- 通过Scrapling解析公开资料，记录来源、时间、图注与文档链接，去重、检索并蒸馏经审阅的工作方法。
- 以技术知识卡学习节点构造、施工工序、材料参数与专业系统；支持工序、参数适用性及指定端子图练习，按[接单能力矩阵](references/professional-learning.md)补齐主题。
- Windows下通过本项目MCP服务端附着已运行的AutoCAD，读取文档和实体；写入需显式会话开关、文档身份及操作ID。

## 快速运行

需要64位Windows与首次安装依赖所需的网络。启动脚本自动准备独立Python3.11环境；基础离线功能也可在Python3.11/3.12的其他系统上使用uv运行。

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action health
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action generate -Spec .\examples\two-room.json -Job demo-001
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action research -ResearchAction status
```

重复生成同一job和输入时只返回已提交结果；同名不同参数拒绝执行。输出在outputs/job。示例尺寸均为示范设计采用值，不能当作现场实测。

MCP宿主的command使用独立环境Python，args为`["-u", "<项目目录>/scripts/entry.py", "serve"]`。先调用cad_adapt_session与cad_tool_schema，读取真实工具目录和参数，再执行。模型身份缺失时返回unknown。

## 范围与来源

项目中的墙体与开洞生成、任务事务、局部编辑、MCP服务和AutoCAD桥由本项目实现；仓库不分发其他CAD服务项目的源码、模板或原生插件。公开资料研究、检查及求解模块延续本项目作者此前维护的代码。基础库作为外部依赖安装，各自许可证见[依赖与资料说明](DEPENDENCIES.md)。

首版支持中心轴直线墙、同一墙段内的门窗、闭合外墙包围的房间和矩形排布。曲墙、任意图片精确复绘、三维BIM、原生插件、DWG/PDF出图及全专业规范审查不属于已实现范围。图纸资料分类来自文字和图注，不能当作逐图验收；国外案例参数不自动进入项目输入。

默认不修改活动CAD，不启动/重启应用，不切换活动文档，不取消用户命令，也没有原始LISP、任意命令或桌面控制入口。AutoCAD实际读写受运行环境影响；测试使用的模拟对象只证明接口保护，不代表所有AutoCAD版本已实机验证。

0.2.1增加[墙地防水连续性原理训练](references/waterproof-training-2026-11-04.md)：生成并回读原生DXF示意，识别断点与缺失上翻。它使用无工程单位的任意坐标，不构成施工节点设计。

## 开发与验证

此前已验证离线出图、门窗局改及中文样图。0.2.0新增技术知识卡和限定练习，首批为厨卫防水及接地系统，见[实际技术学习记录](references/technical-study-2026-11-04.md)。0.1.1从实际原文与三张图中新增两条方法，并增加四个布局回归用例和真实MCP拒绝检查，见[学习与应用记录](references/learning-review-2026-11-04.md)。最终包的独立环境测试证据写入runtime/verification/release-smoke.json。AutoCAD实机附着仍待单独验收；本轮资料学习未操作当前CAD。

```powershell
uv sync --python 3.11 --extra dev --no-editable
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_release.py
```

发布包只包含源码、示例参数与必要参考；不包括本机图纸、采集数据库、预览缓存、登录数据、环境变量或历史日志。MIT许可仅覆盖本项目代码，不授予第三方资料的再分发权。

## 相关链接

[Skill入口](SKILL.md) · [MCP与使用范围](references/usage.md) · [资料研究](references/drawing-research.md) · [依赖](DEPENDENCIES.md) · [许可证](LICENSE)
