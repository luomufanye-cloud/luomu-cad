---
name: luomu-cad
description: CAD参考图复绘与验收、语义轮廓评测、离线DXF、CadQuery参数化STEP、IfcOpenShell构件与FreeSewing纸样，以及施工节点学习。按交付物选择入口，复绘须校准尺度并对照参考。活动AutoCAD仅通过本地Windows的MCP操作。
---

# Luomu CAD

作者：[luomufanye-cloud](https://github.com/luomufanye-cloud) · [MIT](LICENSE)

0.11.0 的二维参数化构件及三维应用流程由本项目独立实现。调用现有工具接口，按源图选择符号与参数；新符号的线稿样式不作为旧图库逐笔复制的承诺。几何内核和文件格式库继续使用其真实依赖名称。

先根据交付目标选择路径，只读取相应参考。整个文件夹是技能资源，不能只复制本文件。输出以实际文件和回读结果为依据；未执行的工作不得报告成功。

## 默认独立交付验收

客户图纸交付先读[需求与独立交付验收](references/customer-delivery.md)，冻结原始任务书、全部需求编号、图种和文件格式；通过 `workbench_industry` 选择行业独立图种及标准，不跨行业借用规则。完整仓库安装验证会配备 [luomu-cad-reviewer](agents/luomu-cad-reviewer.md)，具体宿主配置与加载条件见[安装说明](references/reviewer-installation.md)。在真实客户项目首次使用时核查原生角色，缺失则运行随包安装器到该授权项目，不覆盖已有用户代理。

交付前默认把原始要求、源图和最终文件交给该子代理独立审查，不给生成者通过结论或预期答案；它不绘图、不替客户删项。通过 `workbench_review_agent` 准备原件 packet、启动固定的独立审查进程，并用同一 operation_id 查询真实执行证据，具体参数读工具 schema 和[后台审查接口](references/review-agent-jobs.md)。按当前宿主选择执行器：Codex 使用获授权的 CODEX_HOME；CodeBuddy/HY4 使用 host=codebuddy、获授权的 CODEBUDDY_CONFIG_DIR 和当前主会话 model ID，角色 model=inherit。使用所选账号须显式 opt-in，具体参数以 schema 为准；不切换 Provider、权限或认证。已有宿主独立子代理也须保留真实子会话及实际读取记录，不能仅凭“已启动”的文字声明。

审查进程只读取本单哈希锁定的原件和实际图像；缺原件、缺读取、未完成或发现问题都不能放行。后台 `ready` 只代表独立报告可用。将该报告绑定回原合同，再运行 `workbench_delivery` 或随包 `verify_delivery.py` 重新检查实际文件及全部需求；DWG 最终验收另须同一活动 MCP 会话的受信原生回读。构建工具 `ok`、版本发布和测试通过不代表客户验收。角色配置和行为评测不代表模型权重训练。

## 标准是绘图与交付的基础

室内外、商店、空间、景观、建筑、结构、给排水、电气、电器电子、服装、产品及机械任务，先按[分专业绘图与实测验收](references/professional-cad.md)选本次专业和图种。`workbench_professional` 提供专业模板、实际轮廓/间距/方向/标注测量及线重、多段线宽度检查。依据原图或任务书填写测量目标，执行后检查具体失败项，再回到识读或绘制阶段修正。图种、专业语义、最终纸面表达均需对应证据。

实际绘图开工先按[标准基础与交付依据](references/standards-foundation.md)确定地区、专业、阶段、用途及合同体系，通过workbench_standards查[跨行业标准索引](references/standards-catalogue.json)。区分通用/专业制图、专业设计、制造施工验收、数据交付四层；核实正式版本、实施/替代关系与适用条文，再对应本图检查和证据。题录、教材、草案及测试数量不能代替正文与项目验收；未覆盖行业继续查证，不套建筑模板。

交付前建立绑定最终图纸的标准依据记录并运行scripts/verify_standards.py；完整复绘检查须传--standards-manifest。参考复绘以reference_only限定忠实度，发现原图不规范只报告差异，不擅改设计，也不宣称工程合规。规范复核需已读条文、逐项检查和证据；缺项保持未完成。专业审查、签署及现场验收独立办理。资料阅读与安装/原创训练不冒充项目交付，不因此连接CAD。

绘图前先读[模型调用与交付检查](references/model-workflow.md)，以原始要求固定活动CAD/离线DXF目标及图纸内容；调用cad_adapt_session传入task_target和deliverable。不能把明确的CAD内绘制自动改成离线出图，不能以生成器缺少内容为由交付缺家具、缺标注的平面。开放设计先核对房间功能、面积口径、入口动线、设备家具及开门关系；不为绕过工具限制移动门位。明确的启动任务可通过cad_start执行；普通读取、连接失败和资料任务不自动启动。

自由设计涉及家具时先读[家具关系与使用空间](references/furniture-placement.md)：先确定主家具靠墙段、正面方向、关联对象与操作通行空间，再计算坐标；独立摆放须有功能依据。furnished_plan逐件声明placement、clearances及clearance_basis，不能把不碰撞或矩形求解成功当成布局合理。参考复绘仍按原图，不自行重排。

## 忠实复绘与修改

机械、产品三维零件的建模、孔径数量、尺寸及修改范围检查，读[三维实体建模与量测验收](references/solid-model-review.md)，使用 `workbench_solid` 的独立运行时。先写独立特征及尺寸要求，再构建 STEP、回读、检查四视图；修改时按原坐标核对增加和去除体积。命令成功不等于要求通过，结果不明先用原 key 查询 `run_status`。该入口按任务需要调用，不改变二维复绘或活动 CAD 路径。

图像到结构、参数化实体、IFC 构件或服装纸样任务，按[Luomu CAD 方法与评测](references/cad-method-distillation.md)加载本次需要的方法。模型识读保留类别、轮廓、宿主与空间关系，独立标注使用 `scripts/evaluate_scene.py` 统计漏识别、错分类和定位误差。关系验收同时查看 `semantic_relations`，核对关系两端类别与几何匹配；相同类别、完全重叠的多个对象需复核身份歧义。机械/产品可通过 CadQuery 原装内核生成并重读 STEP，建筑可通过 IfcOpenShell 验证洞口布尔和构件关系，服装可通过 FreeSewing 原装设计生成曲线纸样。具体安装与正常调用见[内核入口](references/cad-engine-usage.md)。每次记录原图对照、执行结果及未检项。

遇到“1:1复刻、一比一、照原图、不改设计”时，先读[忠实复绘与标注验收](references/faithful-redraw.md)，采用复绘路径。模型空间真实单位只是条件之一，还须保留指定视图内的构件、开口、文字、尺寸、符号、图名和比例说明；不得自行优化、补设计或裁掉内容。资料缺项不产生自由设计授权。

图片与扫描页复绘先按[Luomu CAD 图像识读](references/image-reading.md)选择实际需要的模块。模块提供文字和版面识读、局部放大、空间定位与 PDF 读取入口，本地文字识别通过 RapidOCR 执行 Paddle 系列模型。实际查看工具返回图片，记录形状、方向、连接、文字及不确定项，再交给现有源图清单。按需读取单个模块，运行依赖、固定来源和实测边界见该参考。

栅格几何与CAD交互按[栅格复绘与交互检查](references/raster-redraw-quality.md)选择适用部分。图片先识别构件、验证代表区域，再批量绘制；家具线稿不能用像素噪点碎面替代。仅图片无尺寸且已明确按图复绘时允许未定尺源坐标，保持units=0并记录scale依据，不伪造毫米。栅格清单须有独立构件范围、表达预算和适用门关系；生成成功不等于图面或交互通过。

PDF复绘还须读[PDF文字、线宽与填充转换](references/pdf-presentation.md)。先运行preflight记录实际Skill目录、源码/运行时版本及检查器哈希；新任务使用一致的当前版本。使用随包坐标、字形、线宽和填充辅助函数，不能把字号当字高、控制点当拟合点、所有线统一加粗或把每个填充子路径独立涂满。图面对照使用一致背景；活动CAD另查原生显示。

矢量PDF使用[PDF源对象提取](references/pdf-source-import.md)的workbench_pdf_inventory，输入两方向独立量测校准和实际字体映射，再把完整源清单交给workbench_redraw；不能另写丢弃裁切、填充孔洞或文字间距的转换器。调用cad_adapt_session时同时传source_format=pdf。提取发现具体不兼容对象时，修复该对象的转换能力或保留可追溯的人工重建依据，再重跑原始参考；不能把失败项从清单删除后报告完整。

PDF 圆端帽、圆连接的矢量实线可按该流程转换；实际出图仍须按目标纸张和比例比较 PDF，检查线重、文字与裁切。扫描或图片 PDF 会被明确拦截，转入图片识读流程，不能伪称已得到矢量图元或原生尺寸语义。

PDF矢量提取只得到图形，不能代替可编辑CAD语义。尺寸必须重建为原生DIMENSION，并核查定义点、实际测量、样式及图面；不能把线加数字当作合格标注。曲线不能无误差依据固定采样，线宽颜色不能单独决定构件类别。只有明确要求静态图形转存时才使用静态标注路径，并如实标注其性质。

复绘调用cad_adapt_session时指定deliverable=faithful_redraw，按独立源清单调用workbench_redraw统一构建原生图元，避免模型临时重写转换逻辑；不使用两房示例或布局优化器替代参考。先按[源图清单与交付检查](references/redraw-source-gate.md)建立独立源清单，再生成reference_map；运行verify_redraw.py时提供源清单、原文件和绑定当前输出的实际对照记录。缺项、残留静态尺寸、字体映射问题或过期记录不能按完整复绘交付。structural-only只是局部诊断，不是交付通过。修改从最新基线做增量变更，保留先前修正并比较范围外对象，不重跑旧脚本覆盖整图。

局改检查使用最新基线文件及其SHA256，显式列出允许修改和新增的对象；范围外对象、共享样式、匿名尺寸显示块或多余构件发生变化均须修复。原图有尺寸或文字时不得用空清单规避检查。几何定义更新后还要核对显示文字，防止图上仍显示旧数值。复绘契约的字段及连续两轮改图验收见上述专题；每个失败对应到源图位置和对象，修复后重查受影响内容。

## 门窗、墙体与家具组件

需要房间级平面、地面/天花完成面、墙面立面、定向剖面和带目录的PDF图册时，读[共享项目与图册联动](references/shared-project-atlas.md)，使用 `workbench_project`。同一份项目数据维护完成面边界、墙厚、门窗宿主、柜体、标高、材料编号、图号和跨图索引；修改必须新建修订副本，并校核受影响视图及保存后的原生尺寸。此入口当前是明确几何的房间图册，不含灯具回路、给排水拓扑、铺装排版、构造层/设备深化，不能称作19类成套施工图完成。

柜体需要平面、正立面和侧剖时，读[柜体共享尺寸与多视图](references/casework-multiview.md)，使用 `workbench_casework`。先区分柜身高/含收口总高、正面模数/内净空、成品宽/墙间净宽，板厚和内部标高须有明确输入。不能拿平面图库高度字段代替立面生成；修改后回读共享尺寸、原生标注及显示图元，按实际比例查看PDF。该入口不承担五金孔位、生产开料或整套室内施工图。

直墙平面图中的门窗、家具和洁具按[Luomu CAD 构件库](references/house-plan-components.md)查询并调用 `workbench_components`。输入必须明确墙体宿主、洞口宽度、沿墙位置、开向与铰点侧。组件入口共同生成切洞墙体、门扇和开启弧，并检查导出的原生几何。需要分门窗管理时使用 `opening_layer_mode=by_type`，依据本次项目或源图设置 `lineweights_mm`，检查实际实体线重及多段线宽度。先验证代表门墙节点，再扩展重复实例。

复绘先按源图核对组件轮廓、尺寸和方向。重绘任务使用旧回读数据时，需要重新核查门墙关系和源图差异。门扇压墙、铰点离墙或圆弧半径不等于对应门扇宽度的旧几何必须修正后再复用。已有图库包含模型生成方法，实际图片识读与专业出图验收继续逐项验证。

## 环境与任务选择

读取参考DXF或清点构件先按[源图、套块与尺寸链核对](references/cad-source-intake.md)固定视图、单位和对象路径。使用workbench_source_inventory保留套块变换、原始文字与未支持项；轴线、墙面、洞口边不得相互替代。workbench_dimension_chains检查明确特征的分段与总长冲突；它不自动识图或改墙。按图例核对墙体状态、门轴开向与设备符号，不能凭颜色判承重、凭房间功能补门或按距离删除同名构件。

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

## 曲墙、复绘构建与文件交付

执行参数与例子见[执行工具](references/execution-tools.md)。圆弧墙使用workbench_curved_walls，显式给出圆心、半径、厚度、起角/扫角及按轴线弧长定位的洞口；不把弦长当弧长。输出原生ARC/CIRCLE并回读。固定纸张/视图范围/比例的矢量PDF用workbench_export_pdf，不自动缩放迁就纸张。活动图纸另存DWG用cad_save_as，成功后采用返回的新document_token。源清单复绘用workbench_redraw，生成成功后仍需原图对照；不把清单构建工具称作任意图像的自动理解器。

## 离线制图

新建图、中文乱码或尺寸界线调整先读[中文显示与尺寸界线](references/text-and-dimensions.md)。同时验证 Unicode 内容、字体文件/字体族及宿主原生显示；离线预览的字体替代不等于 CAD 显示通过。短界线用固定长度和起点留白控制，保留测量定义点及数值；尺寸链与墙体、阳台和轴号的间距另做图面检查。临时绘图脚本同样执行这些检查，不能绕过统一验收。

以下参数化生成步骤适用于新建参数图。已有参考的忠实复绘先走上述复绘路径，不把参考改写成示例户型来迁就生成器；已有图局改先核对最新文件及目标对象。

先定位技能的实际目录。Windows首次文件任务运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "<技能目录>\scripts\run.ps1" -Action verify
```

安装条件、依赖下载和宿主MCP配置见[使用说明](references/usage.md)。仅在任务需要并满足运行条件时准备环境，不把每次读取Skill变成安装流程。

1. 参照examples/two-room.json组织毫米参数；区分设计采用值与实测值。缺尺寸时先补关键输入，不从图片猜施工尺寸。
   示例只演示参数接口。带家具任务使用deliverable=furnished_plan，并明确floor_boundary、furniture、逐房间furniture_requirements及clear_zones；不得把示例的墙体结构直接当作新设计。
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

全部实时操作只走MCP；COM仅在服务端。写入需要任务授权、-LiveWrites服务开关、文档token和唯一operation_id。结果不明先查cad_operation并回读实体，不重复绘制。禁止GUI、桌面截图、客户端直连COM及任意LISP/命令。明确要求启动时使用cad_start(operation_id, explicit_request=true)，在启用活动写入的MCP会话内执行；已有实例直接复用，不重启、不取消命令。连接恢复规则见[使用说明](references/usage.md)，仅在平台与依赖满足时重试安全读取；暂停、取消及不可恢复的配置错误停止重试。保存与出图按任务范围执行。

明确的新图或打开任务使用cad_new_document或cad_open_document；返回token后再绘制和回读。另存后用新token，交付DWG须按本单要求实际关闭、重开并比较实体。cad_close_document仅关闭本MCP会话创建/打开且已保存、DBMOD=0的图纸，拒绝丢弃未保存编辑；cad_activate_document按精确名称恢复原活动文档。cad_preview生成CAD原生WMF，必须实际查看并检查覆盖范围；非空或签名正确不能证明完整。需要原生交付时使用cad_delivery_snapshot；已有原始DXF可用cad_native_correspondence_preview核对完整原生几何、尺寸显示和样式后生成绑定事实哈希的全范围图像，明确它是回读数据的离线渲染，不能称作原生打印。冷附着、离线JSON和旧截图不能代替当前会话回读。可复现的独立实机流程见[原生CAD验收](references/native-validation.md)。

## 节点学习与交付

按[专业学习清单](references/professional-learning.md)定义完整主题，覆盖材料、构造、接口、计算、工序、养护、检验及条件变化。技术内容用workbench_technical保存来源和应用证据，通用方法用workbench_learn；工程参数不成为全局默认值。采集后继续原文与关键图研读、复绘、错误诊断和迁移练习。主题完成以全部考核条目通过为依据，练习与现场验收分别管理。

管口选型与工况变化先查[管口材料分支与节点应用](references/pipe-node-application-training.md)：普通淋浴、间歇蒸汽入口和连续蒸汽入口分别匹配材料；不能把一般用途覆盖专门排除条件。目录开口、公称管径、实测外径及胶缝尺寸分别取证。答题须独立评阅，脚本内固定答案只算示例；参数练习实际回读平剖面和尺寸，不能替代材料与水密检验。

暖通练习见[安装与水力训练](references/fan-coil-training-2026-11-04.md)，管根练习见[界面与完成面变化](references/pipe-root-training-2026-11-05.md)。改造先查[现状与情景](references/learned/project-state-and-scenario-gates.md)；布局先查[边界与工具能力](references/learned/layout-geometry-capability-gates.md)，不支持的边界或旋转约束不得静默删除。

发布包只包含自有源码、原创归纳和示例；来源与依赖许可保留，原始资料和运行记录不公开。[更新记录](CHANGELOG.md) · [依赖说明](DEPENDENCIES.md)
