# 曲墙、源清单复绘与文件执行工具

日期：2026-11-06

摘要：统一MCP入口提供可编辑复绘构建、圆弧墙、固定比例PDF、显式启动和DWG另存。功能实现、离线运行、协议模拟和AutoCAD实机验收分别记录。

## 源清单复绘

调用`workbench_redraw(job_id, source, inventory)`。source是Skill目录内的私有原始参考文件路径，inventory按[源清单协议](redraw-source-gate.md)提供源SHA256、页码、范围和逐对象预期；保留原文件，临时资料不进入公开包。

按清单顺序构建LINE、ARC、CIRCLE、带bulge的LWPOLYLINE、控制点SPLINE、TEXT、线性DIMENSION和实心HATCH。字体文件、字体族、基线、字高、宽度、旋转及线宽色彩来自核对后的源清单。TEXT的中文TrueType字体需同时给出font与font_family。样条使用控制点，不把控制点改为拟合点；尺寸使用原生测量，不把display_text写成固定覆盖值。

返回DXF、source-inventory.json、mapping.json和source-check.json。构建后回读与源清单比较；源哈希不符、未知类型、格式化尺寸或未定义线型明确失败。源清单不是从输出反推的答案。此工具负责确定性构建，PDF/图像内容提取、尺寸校准与图面对照仍是复绘流程中的实际步骤，不由工具名称代替。

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

另存接口不关闭、不切换或重新打开图纸。文件签名与路径回读不替代重新打开后的实体/图面验收；需要该级验收时按交付范围完成后再声明。

## 验证范围

| 能力 | 当前证据 |
| --- | --- |
| 圆弧墙/洞口 | 原生实体保存回读、独立弧长/厚度检查、整环接缝及错误输入回归，真实stdio MCP调用 |
| 源清单复绘 | 原生尺寸等对象构建、源哈希拒绝及独立清单回读，真实stdio MCP调用 |
| PDF导出 | 实际PDF文件、物理MediaBox、指定比例参数、矢量内容、源文件保持及MCP调用 |
| 启动与DWG另存 | 协议模拟覆盖已有实例、显式启动、失败不重放、文档身份更新、路径冲突；本次未执行AutoCAD原生验收 |

## 相关链接

- [MCP使用说明](usage.md)
- [Autodesk SaveAs](https://help.autodesk.com/cloudhelp/2024/KOR/AutoCAD-ActiveX-Reference/files/GUID-ED0D0B02-25FC-4ED2-9DEE-2B0C9AA9416A.htm)
- [ezdxf绘图导出](https://ezdxf.readthedocs.io/en/stable/addons/drawing.html)

软件资料检索日期：2026-11-06。
