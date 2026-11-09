# Luomu CAD 技术参考与实现

日期 2026-11-07

摘要 本轮把公开论文中的结构表示、执行反馈及独立几何评测方法接入现有 Skill，并调用 CadQuery、IfcOpenShell、FreeSewing 的原装实现。方法整理、接口适配和运行检查由本项目实现，识图效果通过独立测试集比较。本模块采用现有模型和计算内核。

## 来源选择

GitHub 星数为 2026-11-07 检索时快照。检索覆盖 CAD、参数化建模、floorplan reconstruction、服装制版等主题。星数与可用输入、输出、许可和运行条件共同决定采用范围。

| 参考项目 | 星数 | 采用内容 | 本轮处理 |
| --- | ---: | --- | --- |
| FreeCAD | 35210 | 成熟参数化 CAD 与图纸工作台 | 保留候选，当前内核路径选 CadQuery |
| CadQuery | 6073 | Python 参数化 BRep、布尔、拉伸、放样、STEP 与 SVG | 安装 2.8.0，增加通用执行与导出回读入口 |
| build123d | 3646 | OpenCascade 参数化建模 | 保留候选，避免同时加载重复内核接口 |
| IfcOpenShell | 2936 | IFC 构件、洞口宿主、填充关系、几何布尔 | 安装 0.9.0.post1，回读 IFC 关系及净体积 |
| FloorplanTransformation | 686 | 角点预测后进行全局整数规划约束 | 提取墙连接和门宿主检查思路，旧 Torch7 权重未部署 |
| FreeSewing | 488 | 人体量体、参数化曲线、缝份、纸样 | 安装 4.10.2，通过原装设计导出 SVG |
| RoomFormer | 343 | 房间角点与多边形联合预测 | 记录为研究候选，需匹配其输入域 |
| CAD-Coder | 218 | 图像到可编辑 CadQuery 程序，执行与几何分别评估 | 接入程序执行、STEP 重读与三视图输出 |
| Raster2Seq | 80 | 带语义多边形序列表示 | 采用对象与轮廓交接格式，预训练权重为非商业许可 |

来源快照、固定提交与许可见 [来源记录](cad-upstream-sources.json)。本轮执行记录覆盖 CadQuery、IfcOpenShell 和 FreeSewing；表中的其他研究候选按各自运行条件另行准备。`wy51ai/floorplan-3d` 的 3615 星项目主要以手工结构数据构建网页展示，本轮适配集中于 CAD 文件与几何内核。`flowful-ai/cad-skill` 的 716 星项目采用 PolyForm Noncommercial 许可，商业运行时采用其他实现。

## 从论文到执行步骤

### 结构识读

FloorplanTransformation 先提取墙角、门端点等语义几何，再通过整数规划组合构件。迁移时先建立墙段连接图，逐一对应洞口宿主、交点、端点、厚度和房间边界。局部补线要重新核对相邻房间与门窗关系，保留原图坐标和观察依据。该项目的 PyTorch 移植注明测试不足，执行条件需单独复现。[论文与官方项目页](https://art-programmer.github.io/floorplan-transformation.html)

Raster2Seq 把房间、门和窗表示成有类别的多边形序列。当前统一使用 `cad-scene/1` 交接对象 ID、类别、多边形和关系，避免轮廓与名称在绘制时脱节。输入裁剪、缩放、旋转须逆变换到统一源坐标后再交接。[论文](https://arxiv.org/abs/2602.09016)

本轮新增 `scripts/evaluate_scene.py`。独立源标注与模型预测按轮廓 IoU 做一对一匹配，输出漏识别、多识别、错分类、质心距离、轮廓 Hausdorff 距离和关系错误。分类错误不会被相似轮廓隐藏。门洞宿主关系采用 `hosted_by`，方向按起点与终点保留。房间相邻关系采用统一方向或双方记录，由数据集协议明确。

```json
{
  "schema": "cad-scene/1",
  "source_sha256": "填写原图64位SHA256",
  "coordinates": {"units": "pixel", "y_axis": "down", "width": 1600, "height": 1200},
  "objects": [
    {"id": "W1", "label": "wall", "polygon": [[10,10],[100,10],[100,20],[10,20]]},
    {"id": "D1", "label": "door", "polygon": [[30,10],[50,10],[50,20],[30,20]]}
  ],
  "relations": [{"type": "hosted_by", "from": "D1", "to": "W1"}]
}
```

参考标注另有 `annotation.reviewer` 与 `annotation.method`，记录真实标注者和审阅方法。评测者保管参考标注。预测轮只读取源图、任务要求、允许的尺寸依据与当前技能，评测结束后才显示逐项错误。参考标注被提前提供给生成模型的结果单列为有答案辅助实验。

```text
python scripts/evaluate_scene.py reference.json prediction.json --source source.png --report evaluation.json
```

采用同一源图与坐标系，默认匹配阈值 0.5。发布分专业 precision、recall、定位误差和关系错误，同时保存两份输入哈希。空类别指标保留 null。当前评测入口支持二维多边形。细线对象需要可解释的实体厚度轮廓，曲线与原生标注继续走现有专业检查器。

2026-11-08 补充语义关系检查。原 `correct_relations` 根据几何匹配和关系类型统计拓扑关系，新增 `semantic_relations` 要求关系两端类别也正确。例如把门识别为窗，即使轮廓和宿主位置重合，语义关系仍计为缺失和多余。该指标沿用同一次几何优先匹配，精度及召回率分母为空时为 null。独立验证仍依赖人工标注和真实图纸对照，不能据合成样例声称识图准确率提高。

同日修复等重叠度下的匹配不稳定问题。匹配优先最大化对象配对数，再最大化六位整数精度的 IoU 之和，两者相同时优先类别一致。对象输入按 ID 排序，重排对象列表不会改变同一输入的结果。完全重叠且类别相同的多个对象仍可能存在身份歧义，关系结果需要对照源图审查。该评测使用 OR-Tools CP-SAT 整数目标，不包含第三方模型或权重。[CP-SAT 官方文档](https://developers.google.com/optimization/cp/cp_solver/) · [依赖项目许可](https://github.com/google/or-tools/blob/stable/LICENSE)

参考 CVPR 2024 对主体、关系和客体三元组的表述，以及 MIT 许可的公开场景图评测项目。此处仅采用关系评测思路，未引入其代码或模型权重。[论文](https://openaccess.thecvf.com/content/CVPR2024/html/Li_Leveraging_Predicate_and_Triplet_Learning_for_Scene_Graph_Generation_CVPR_2024_paper.html) · [参考项目与许可](https://github.com/microsoft/scene_graph_benchmark)

### 参数化实体与执行反馈

CAD-Coder 使用 CadQuery 程序表达可编辑几何，并区分可执行性与实体相似度。当前模型按明确的尺寸及特征关系写 `result`，由原装 CadQuery 执行，导出 STEP 后重新打开，测量包围盒、实体数和体积，输出前、顶、右视图供原图对照。已有模型可使用完整 CadQuery API，实例文件仅用于安装测试。[论文](https://arxiv.org/abs/2505.14646)

Ortho2CAD 的多视图方法用于整理投影关系与尺度约束。先核实投影法、视图名称、隐藏线及标注指向，建立同一特征在各视图的对应关系。尺寸冲突返回原图核对。三维候选的各视图应分别比较，轮廓一致和内部孔槽结构均需证据。[论文](https://arxiv.org/abs/2607.08891)

Pen2STEP 提供多视图、OCR 尺寸、候选程序和执行评估的公开流程。其默认提示含估计整数尺寸，部分补救会改变结果几何。此次采用多视图对应、明确尺寸和执行记录方法，忠实复绘中的尺寸与几何修改仍须源图依据。其公开回放结果与本项目实际模型运行结果分别记录。[项目实现](https://github.com/unes21/pen2step)

### 建筑构件关系

IfcOpenShell 的 `feature.add_feature` 将洞口与宿主关联，几何引擎执行实际减除，`feature.add_filling` 建立门窗填充关系。本轮回读 `IfcRelVoidsElement`、`IfcRelFillsElement` 和减洞后的墙体净体积。新增模型可使用完整 IFC API。柱梁、楼板、空间和设备网络按真实专业对象继续扩展，并依据该对象的专业检查项验收。[官方 API](https://docs.ifcopenshell.org/autoapi/ifcopenshell/api/feature/add_feature/index.html)

### 服装曲线制版

FreeSewing 以量体数据驱动原装纸样设计，输出曲线、缝份与标记。本轮通过可配置模块路径和导出类接入设计，已安装 Benjamin 领结用于真实制版测试。其他款式须安装对应纸样设计包并测试所需量体字段。工业 DXF/AAMA/ASTM 交换、版型实穿和生产工艺另行实测。[FreeSewing 源码](https://github.com/freesewing/freesewing)

## 与当前专业技能衔接

1. 按 [专业工作流](professional-cad.md) 选专业、图种、中国适用标准与项目交付物。
2. 图片识读使用现有 OCR、局部图像工具和统一对象记录。每个墙、门、窗、家具或零件特征保留位置与来源。关键歧义在生成前处理。
3. 建筑平面继续进入现有源清单及 DXF 构建。IFC 交付走建筑构件 API。机械与产品实体走 CadQuery。服装纸样走对应 FreeSewing 设计。各入口保留真实输出格式。
4. 内核执行错误回到具体特征与 API 调用。保留源程序、错误、修改理由、导出文件哈希。改变尺寸或拓扑的修正重新对照原图。
5. 重新打开输出并运行专业测量。DWG 的活动操作继续通过 CAD MCP。纸面线重、布局、比例、文字和尺寸检查沿用现有流程。
6. 同一专业积累独立源图测试集，用固定模型、版本、提示与预算做更新前后对照。报告逐图与汇总差异，并保留失败样本。

给排水、建筑电气、电子、电路、结构、景观与室外任务继续采用原专业检查和标准来源。IfcOpenShell 为对象表达提供基础，系统计算、电子 ERC/DRC、结构安全、生产工艺等仍需要各自专用实现与真实验证。

## 运行与相关链接

- [安装与调用计算内核](cad-engine-usage.md)
- [实测记录与边界](cad-engine-validation.md)
- [现有图像工具](image-reading.md)
- [专业检查](professional-cad.md)
