# 曲墙、源清单复绘与文件执行工具

日期：2026-11-07

摘要：统一MCP入口提供PDF源对象提取、可编辑复绘构建、圆弧墙、固定比例PDF、显式启动和DWG保存重开。文件验收与原生运行验收都有独立执行入口。

## 源清单复绘

调用`workbench_redraw(job_id, source, inventory)`。source是Skill目录内的私有原始参考文件路径，inventory按[源清单协议](redraw-source-gate.md)提供源SHA256、页码、范围和逐对象预期；保留原文件，临时资料不进入公开包。

按清单顺序构建LINE、ARC、CIRCLE、带bulge的LWPOLYLINE、控制点SPLINE、TEXT、线性DIMENSION、实心HATCH和带原生XCLIP的裁切块。字体文件、字体族、基线、字高、宽度、旋转及线宽色彩来自核对后的源清单。TEXT的中文TrueType字体需同时给出font与font_family。样条使用控制点，不把控制点改为拟合点；尺寸使用原生测量，不把display_text写成固定覆盖值。

返回DXF、source-inventory.json、mapping.json和source-check.json。构建后回读与源清单比较；源哈希不符、未知类型、格式化尺寸或未定义线型明确失败。源清单不是从输出反推的答案。矢量PDF先调用[workbench_pdf_inventory](pdf-source-import.md)实际提取；extraction_complete=false的清单不能构建成完整交付。

工具成功后，使用返回的清单与映射运行完整verify_redraw入口，并补当前文件的实际原图对照。仅凭构建成功不报告整图忠实复绘完成。

## 圆弧墙和弧长洞口

调用`workbench_curved_walls(job_id, spec)`，例如以下原创毫米输入：

```json
{"walls":[{"id":"C1","center":[1000,2000],"radius":3000,"thickness":240,"start_angle":330,"sweep_angle":180,"openings":[{"id":"O1","offset":1000,"arc_width":900}]}]}
```

radius为墙轴半径，thickness沿径向均分；角度为度，逆时针sweep_angle在(0,360]内。洞口offset与arc_width均沿轴线弧长计算，不能把弦长直接填入。输出内外原生ARC及端部LINE；完整无孔环墙输出两个CIRCLE，整环有孔时不添加人为接缝。保存后核对每个实体的中心、半径、角度或端点。

洞口表示实际去除的墙体区间，不推断门窗产品、门轴、扇形或框料。多面曲墙之间的交接、结构构造、与直墙的相交收口应按明确节点另行定义；不能以边界画成就声称这些内容已完成。

活动CAD中需要原生圆弧时，cad_mutate支持operation=arc，arguments为center、radius、start_angle、end_angle和可选layer。输入角度为度，服务端只转换一次为ActiveX所需弧度；跨0度仍按逆时针处理，整圆用circle。该分支已做协议回归，原生运行验收单独记录。

## 固定比例矢量PDF

调用`workbench_export_pdf(job_id, source, paper_mm, window_mm, scale, margin_mm=10)`：

```json
{"job_id":"a3-print","source":"outputs/example/plan.dxf","paper_mm":[420,297],"window_mm":[0,0,18000,12000],"scale":50,"margin_mm":10}
```

source必须是outputs内已保存的毫米DXF。paper_mm为纸张宽高；window_mm为模型范围[xmin,ymin,xmax,ymax]；scale=50表示1:50。按真实纸面尺寸居中输出，不自动fit、不紧裁纸张；范围按该比例放不下时返回错误，由任务决定更换图幅或比例，不能静默缩小。

结果为矢量PDF及源文件哈希、纸张/模型范围/比例记录，源DXF不变。输出采用离线渲染引擎，不等同AutoCAD PC3/CTB打印；特殊字体、外部参照和代理对象需要核对目标渲染效果。原图复绘的纸面窗口、背景和线宽要求见[表现转换](pdf-presentation.md)。

## 显式启动AutoCAD

`cad_connect`和资料工具保持只读附着行为。任务明确要求启动时，在已获该任务授权且启用`LUOMU_CAD_LIVE_WRITES=1`的持久MCP服务中调用：

```json
{"operation_id":"start-task-001","explicit_request":true,"progid":"AutoCAD.Application"}
```

工具名为`cad_start`。若目标实例已运行则复用；只有系统明确返回无运行实例时创建应用。网络/COM异常不被当作启动理由；不重启、终止应用或取消命令。相同operation_id不会重复启动，发生结果不明时查cad_operation，不重复派发。

返回应用窗口标识后，仍用list_documents、cad_connect和cad_read_entities确认实际文档与运行状态。启动接口不选择图纸，不把应用创建成功当作图纸任务完成。单次CLI call默认只读，显式启动/写入使用已配置的持久MCP会话；服务配置见[使用说明](usage.md)。

## DWG另存

调用`cad_save_as(operation_id, document_token, path)`。path必须是已存在父目录下的绝对.dwg新路径，禁止覆盖已有文件。服务检查当前文档token、写入开关及空闲状态，再执行原生ActiveX SaveAs。

SaveAs会改变当前文档名称。工具核对落盘文件签名、文件哈希和当前文档路径，然后返回新document_token；之后读取和修改必须使用新token。旧操作重试先核对日志及文件哈希，不能在另存后继续携带旧token绘制。

另存成功后，使用cad_close_document关闭本会话所属且已保存的文档，cad_open_document重新打开并取得新token，cad_read_entities核对实体及测量。cad_activate_document可按精确名称恢复原活动文档。不能沿用关闭前的token，也不能覆盖其他已存在文件。

## 原生图面与尺寸样式

cad_preview(operation_id, document_token, path, render_png=true)导出原生WMF或BMP，返回PNG用于实际查看。WMF栅格化按原始逻辑坐标映射，避免通用图像加载器把圆压扁或裁掉文字。预览检查绘制内容，临时缩放后恢复原视图；不使用桌面截图。优先使用WMF加PNG以获得矢量原生预览。

cad_mutate的dimension参数可提供style，逐对象设置TextHeight、ArrowheadSize、TextGap、ExtensionLineOffset、ExtensionLineExtend、ScaleFactor、LinearScaleFactor。例如2.5毫米纸面字高、1:50采用TextHeight=2.5与ScaleFactor=50，真实测量保持LinearScaleFactor=1。样式采用应有本图依据，不改全局尺寸样式，不用固定文字掩盖错误测量。

新建、打开、关闭及预览的完整可执行步骤见[原生CAD验收](native-validation.md)。

## 验证范围

| 能力 | 当前证据 |
| --- | --- |
| 圆弧墙/洞口 | 原生实体保存回读、独立弧长/厚度检查、整环接缝及错误输入回归，真实stdio MCP调用 |
| 源清单复绘 | 原生尺寸等对象构建、源哈希拒绝及独立清单回读，真实stdio MCP调用 |
| PDF导出 | 实际PDF文件、物理MediaBox、指定比例参数、矢量内容、源文件保持及MCP调用 |
| 启动与DWG保存重开 | 2026-11-07实际启动、本机圆弧/尺寸回读、原生预览、DWG另存和重开；操作重试、旧token及路径冲突反例 |

## 相关链接

- [MCP使用说明](usage.md)
- [Autodesk SaveAs](https://help.autodesk.com/cloudhelp/2024/KOR/AutoCAD-ActiveX-Reference/files/GUID-ED0D0B02-25FC-4ED2-9DEE-2B0C9AA9416A.htm)
- [ezdxf绘图导出](https://ezdxf.readthedocs.io/en/stable/addons/drawing.html)

软件资料检索日期：2026-11-06。
