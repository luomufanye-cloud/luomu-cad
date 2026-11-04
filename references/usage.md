# MCP使用与验收范围

日期：2026-11-04

摘要：离线绘图和实时CAD共享协议入口，拥有不同的操作条件和验收范围。

## 离线图纸

spec的walls指定id、axis、thickness和可选closed。openings指定id、wall、kind、offset、width；offset沿墙轴累计测量，不允许跨角或相互重叠。rooms以at定位闭合外墙内的空间。schedules选择doors、windows、rooms；缺失高度与窗台参数在表格中标为待核实，不补造工程值。

workbench_generate输出DXF、PNG、输入参数、QA与manifest。job_id与请求绑定；相同job不同参数拒绝，已提交job验证文件哈希后返回旧结果。出错中断的任务保持待核验，不擅自重放。

workbench_patch_opening需要job_id、source_job、expected_revision、opening_id和changes。改动组为该门窗、宿主墙与关联表格，其他实体哈希逐个核对。外部改过源文件、revision过期、目标不存在或尺寸非法时拒绝套用。

墙体为中心轴直线多段线，先列出的墙拥有交接处，后列墙裁切至已存在墙边。复杂错层、曲面、特殊构造和专业施工审查须另行实现。房间面积来自闭合外墙及实心隔墙区域，不将门洞相连空间合并为一间。

## 实时CAD

以scripts/run.ps1 -Action serve提供MCP；只有已有任务授权才加-LiveWrites。客户端保持同一会话，cad_connect返回document_token，每个cad_mutate同时携带该token与operation_id。支持line、circle、polyline、text、dimension、properties、save；save仅保存已有路径的当前文档，不执行SaveAs。properties仅支持layer/text/height/color。没有删除、启动、任意命令或LISP接口。

活动文档身份改变、命令未结束或写入开关关闭时拒绝修改。cad_operation返回写入断点；started不代表成功，也不能直接用新ID重复执行。完成结果包含可回读的handle。能力边界由工具schema及实际读取结果确定，不宣称全版本支持。

CLI的call用于单次工具请求，默认只读；需要多个连续实时步骤时使用持久MCP会话。status --once是只读附着诊断，不是绘图验收。

## 相关链接

[示例参数](../examples/two-room.json) · [MCP协议](https://modelcontextprotocol.io/) · [AutoCAD AddLine](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-ActiveX-Reference/files/GUID-26C95029-14BB-40B9-9987-49EFC980CB9D.htm) · [AutoCAD AddDimAligned](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-ActiveX-Reference/files/GUID-9F5CE147-3787-4DD9-8028-8E89BF02A357.htm)
