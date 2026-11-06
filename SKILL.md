---
name: luomu-cad
description: 按毫米参数生成和修改离线CAD平面DXF、回读几何，或查阅并训练施工节点资料。操作活动AutoCAD时仅适用本地Windows与MCP；不用于网页户型设计器或无尺寸图片的精确复绘。
---

# Luomu CAD

作者：[luomufanye-cloud](https://github.com/luomufanye-cloud) · [MIT](LICENSE)

先根据交付目标选择路径，只读取相应参考。整个文件夹是技能资源，不能只复制本文件。输出以实际文件和回读结果为依据；未执行的工作不得报告成功。

## 环境与任务选择

- **节点解释、读图方法和学习**：从[技术卡索引](references/technical/index.md)或[方法索引](references/learned/index.md)查具体主题。读取参考资料即可开始，不为解释问题安装依赖、连接CAD或运行采集器。涉及数值时保留出处、版本、单位和采用条件。
- **新建离线DXF或修改已生成图纸**：需要可执行Python 3.11/3.12及子进程的环境和锁定依赖；不需要AutoCAD。Windows使用下述PowerShell入口，其他环境按[使用说明](references/usage.md)准备Python运行时。
- **活动DWG**：要求同一电脑上的Windows、已运行的AutoCAD和可用CAD MCP。纯云端沙箱无法附着桌面CAD。先确认条件，不在不支持的平台循环重连或启动AutoCAD。
- **公开资料研究**：按[研究流程](references/drawing-research.md)限制来源、请求、robots与体积；收集和学习分别记录。

有Python时可运行无第三方依赖的预检：

```text
python scripts/preflight.py --mode reference
python scripts/preflight.py --mode offline
```

预检不安装软件、不访问网络、不启动服务、不探测AutoCAD。缺少Python或本机执行权限时仍可读取参考；文件生成任务应明确缺少的能力，不能编造下载链接或改用桌面操作。

## 离线制图

先定位技能的实际目录。Windows首次文件任务运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<技能目录>\scripts\run.ps1" -Action verify
```

安装条件、依赖下载和宿主MCP配置见[使用说明](references/usage.md)。仅在任务需要并满足运行条件时准备环境，不把每次读取Skill变成安装流程。

1. 参照examples/two-room.json组织毫米参数；区分设计采用值与实测值。缺尺寸时先补关键输入，不从图片猜施工尺寸。
2. 调用workbench_generate，提供唯一job_id和spec。仅有shell时使用scripts/entry.py，经随包真实stdio MCP执行。
3. 门窗局改用workbench_patch_opening，携带source_job、expected_revision、opening_id和changes；创建新副本，核对范围外实体。
4. 回读保存DXF的单位、墙体与洞口、尺寸和关联表，再查看PNG。几何通过、图面检查和专业设计审核分别报告。

可复现的正常、门宽局改、错误输入及知识卡工序任务：

```text
python scripts/verify_tasks.py
```

结果保存在runtime/verification/tasks.json。安装验收使用scripts/verify_install.py；两者都不操作活动CAD。宿主MCP配置与已验证范围见[使用说明](references/usage.md)。

## 活动CAD

先调用cad_detect_versions、list_documents，再cad_connect取得文档token，分页cad_read_entities。多版本明确目标；参数用cad_tool_schema查询，不猜工具协议。模型公开元数据用cad_adapt_session，身份不明保持unknown。

全部实时操作只走MCP；COM仅在服务端。写入需要任务授权、-LiveWrites服务开关、文档token和唯一operation_id。结果不明先查cad_operation并回读实体，不重复绘制。禁止GUI、桌面截图、客户端直连COM、任意LISP/命令及启动或重启CAD。连接恢复规则见[使用说明](references/usage.md)，仅在平台与依赖满足时重试安全读取；暂停、取消及不可恢复的配置错误停止重试。保存与出图按任务范围执行。

## 节点学习与交付

按[专业学习清单](references/professional-learning.md)定义完整主题，覆盖材料、构造、接口、计算、工序、养护、检验及条件变化。技术内容用workbench_technical保存来源和应用证据，通用方法用workbench_learn；工程参数不成为全局默认值。采集后继续原文与关键图研读、复绘、错误诊断和迁移练习。主题完成以全部考核条目通过为依据，练习与现场验收分别管理。

暖通练习见[安装与水力训练](references/fan-coil-training-2026-11-04.md)，管根练习见[界面与完成面变化](references/pipe-root-training-2026-11-05.md)。改造先查[现状与情景](references/learned/project-state-and-scenario-gates.md)；布局先查[边界与工具能力](references/learned/layout-geometry-capability-gates.md)，不支持的边界或旋转约束不得静默删除。

发布包只包含自有源码、原创归纳和示例；来源与依赖许可保留，原始资料和运行记录不公开。[更新记录](CHANGELOG.md) · [依赖说明](DEPENDENCIES.md)
