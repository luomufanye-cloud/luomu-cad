# 分专业绘图与可测量验收

日期 2026-11-07

摘要　本模块提供13类专业任务配置、源依据绑定和二维实测。专业知识检查、工程计算与真实图片识别需要各自的验证记录。实施代码复用 ezdxf、Shapely 与现有纸面比例 PDF 渲染器。

## 开工选择

通过 `workbench_professional(operation="profiles")` 读取[专业配置](professional-profiles.json)，只展开当前专业。商业店铺可以组合 `commercial`、`interior`、`water_supply`、`building_electrical`，电器产品可以组合 `product`、`electronics`。组合取决于委托范围。空间和室外是任务分组，适用标准继续经各专业路由选择。

先确定图种、阶段、地区、用途、单位、参考来源、设计输入和输出软件。创建模板后逐项填写。模板中的 pending 保留为未完成，专业缺失时补充来源和适配。

```sh
python scripts/verify_professional.py --profile interior --profile commercial --report professional-review.json
python scripts/verify_professional.py drawing.dxf professional-review.json --report professional-result.json
```

活动 AutoCAD 的数据通过 MCP 回读。`cad_presentation_snapshot` 连续读取两轮实际样式并比较哈希，返回图层/实体线重、块引用、多段线宽度及显示变量。可通过下列独立MCP客户端调用，记录缺失属性。文件几何检查器消费已授权产生的DXF，活动DWG完整几何对应仍需任务MCP适配器支持。

```sh
python scripts/inspect_live_presentation.py --report live-presentation.json
```

## 专业对应关系

| 专业 | 建图时落实的对象与关系 | 出图内容按阶段和合同选定 |
| --- | --- | --- |
| 空间 | 闭合空间、面积口径、入口、开口、通行与使用净空 | 分区、动线、面积与尺寸 |
| 室内 | 墙体厚度及转折、门铰点与开启侧、窗型、家具轮廓和朝向 | 平面、天花、立面、节点、材料与门窗表 |
| 商店 | 货架柜台、客流员工补货路径、设备定位与机电接口 | 布置定位、立面节点、接口及设备表 |
| 室外 | 测量基准、红线、定位、道路、标高和排水衔接 | 总平、竖向、道路与场地节点 |
| 景观 | 地形、种植编号、铺装、构筑物、水景及专业管线 | 总平、竖向、种植铺装、节点与配套图 |
| 建筑 | 轴网、墙体、开口、楼层标高、平立剖对应 | 各层平面、立剖面、详图及表格 |
| 结构 | 构件截面和编号、配筋、洞口、节点与标高 | 结构布置、构件配筋、节点与说明 |
| 给排水 | 管径、坡度、流向、端口、阀件、设备与系统对应 | 平面、系统、节点、设备材料表 |
| 建筑电气 | 箱柜、回路、负载、线路、安装高度和图例 | 平面、系统、回路表与安装节点 |
| 电器电子 | 器件、位号、引脚、网络、连接点、外壳接口 | 原理接线、装配外形及器件表 |
| 服装 | 裁片、净样毛样、缝份、刀口、经向、配缝和放码 | 样版、尺寸放码、排料及工艺标记 |
| 产品 | 多视图外形、接口、公差、材料工艺、装配间隙 | 零件、装配、接口、BOM及技术要求 |
| 机械 | 投影剖切、中心线、尺寸基准、公差配合、孔轴装配 | 零件、装配、明细表及技术要求 |

表中对象和图种是任务拆分框架。每项是否适用由参考范围、工程阶段和合同确认。配置还给出需要专业人员复核的具体内容。

## 识图与结构重建

先沿用[上游图像读取方法](image-reading.md)取得清晰局部。清单覆盖本次要求的全部对象，给每个对象原图定位、轮廓、特征点、朝向、关联对象和尺度依据。先处理全局坐标与主体结构，再处理开口和关联空间，最后填入设备、家具、文字与符号。

形状采用原图可观测轮廓。矩形家具、符号块、门窗和产品外形都需对照特征点。弧线、曲线和不规则边界用原生曲线表达，保留圆弧半径、圆角、凹凸和朝向。原图局部模糊则记录疑点、补读相邻区域或取得更清晰输入。

检查器使用独立源坐标，与生成结果做双向 Hausdorff 轮廓距离、边界间距、长度、闭合性、面积、方向、原生标注测量和文字检查。源坐标由输出反推会失去独立性。检查器只能核对已录入的源判断，真实识别能力必须使用独立标注样本验证。

## 线条与出图尺度

线重按纸面毫米检查，多段线宽度按模型单位检查。检查器调用 ezdxf 的属性解析，展开块内 ByLayer、ByBlock 和0层继承，另查常量宽度、逐段宽度及块缩放。非等比块缩放进入待复核。CTB/STB、线型比例和最终原生打印效果需要单独回读和预览。

建筑项目明确采用 GB/T 50001-2017 第4.0.1条时，可以在 style 中填写 `building_base_mm`。基本线宽0.5、0.7、1.0、1.4毫米分别对应该表的四组离散值。具体构件采用哪一档须继续按图种及专业条文指定。其它行业按自己的标准或合同给图层设置预期区间。[住房城乡建设部发布页](https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2018/art_17339_234638.html)

输出纸张、窗口范围和比例应明确。现有 `workbench_export_pdf` 调用 `pdf_export.render_pdf` 保留物理纸张尺寸和实体线重。预览阶段同样使用该渲染器或 CAD MCP 原生预览，记录实际输入文件哈希。禁止用固定 linewidth 重画结果后据此判定线宽通过。

## 契约字段

- `source` 指定独立参考文件、SHA256及定位。图片、原始矢量图、设计任务书均可作为来源，需说明坐标对应方法。
- `drawing_sha256` 绑定本轮图纸。`expected_handles` 列出全模型实体清单，辅助图框等实体也计入。源对象清单的完整性继续由复绘验收验证。
- `categories` 对应所选专业，每个存在项至少绑定一种适合该类的测量。范围外项填写 `not_applicable`、依据定位和具体理由。未知项保持 pending。
- `checks` 每项包含唯一 id、kind、源定位、实体 handles 和对应参数。全部数值需有限，公差需为正。
- `style.layers` 按图层声明 `lineweight_mm`、`linetypes` 和 `polyline_width`。均需从项目依据选取。
- `reviews` 保存源覆盖、专业语义与最终图纸交付的实际复核结果、当前图纸哈希和证据文件哈希。

| kind | 参数与实际核对 |
| --- | --- |
| contour | expected_points、tolerance，核对实际曲线与源轮廓 |
| distance | other_handles、range、tolerance，核对两组曲线最短间距 |
| length | range、tolerance，核对曲线总长 |
| closed | expected、tolerance，核对简单闭合边界 |
| area | range、tolerance，核对单个闭合边界面积 |
| angle | expected、angle_tolerance、tolerance，核对单根LINE的有向角度 |
| dimension | range，回读原生DIMENSION测量值并检查文字覆盖 |
| text | expected，按handles顺序核对原生TEXT/MTEXT文字 |
| count | range、types，核对指定实体数量和类型 |

曲线按 tolerance 的四分之一离散后测量，面积单位为模型单位平方。距离值为二维边界距离。管网的连接点、门洞语义和三维空间需要专项判断。曲线测量当前支持XY平面原生LINE、ARC、CIRCLE、ELLIPSE、LWPOLYLINE、POLYLINE、SPLINE，块内几何需建立显式实体映射或服务端展开后的复核数据。

## 交付判定

完整参考复绘继续运行 `scripts/verify_redraw.py`。标准依据中的专业已由本模块支持时，加入 `--professional-manifest professional-review.json`。入口会运行测量、样式和复核记录检查，错误或未完成记录会使完整复绘验收失败。

`technical_checks_passed` 表示本次契约所列的机器检查结果。`review_record_complete` 表示复核证据绑定完整。最终出图仍需核对约定图种、图框图名版本、视图比例、标注、图例、字体、专业表格、外部参照、打印设置和可打开的交付文件。工程安全、施工制造可行性及签署按对应专业处理。

## 标准来源和验证范围

服装制图、CAD和两类数据交换标准已核对现行题录。其全文条款和打版软件兼容性需要后续实测。[GB/T 29863-2023](https://openstd.samr.gov.cn/bzgk/std/newGbInfo?hcno=1D14053761105968EA7436F87327DC81) · [FZ/T 80015-2022](https://std.samr.gov.cn/hb/search/stdHBDetailed?id=F9A74BF1D2B6EC70E05397BE0A0A8DAE) · [样版数据](https://std.samr.gov.cn/hb/search/stdHBDetailed?id=15A65204E7C1ED9FE06397BE0A0A7B4D) · [排料数据](https://std.samr.gov.cn/hb/search/stdHBDetailed?id=15A65204E7C2ED9FE06397BE0A0A7B4D)

景观采用独立标准路由，项目再核实条文和地区适用性。北京地区的设计深度文件仅按其范围采用。[全国城镇风景园林标准化技术委员会公告](https://www.china-stla.cn/news_3/7400134.html) · [北京市园林绿化局标准正文](https://yllhj.beijing.gov.cn/sdlh/ylkj/bzgf/202302/P020230222373447534759.pdf)

建筑工程图纸深度按阶段选取，并继续查项目所在地要求。[住房城乡建设部2016版发布页](https://www.mohurd.gov.cn/gongkai/zc/wjk/art/2016/art_17339_229701.html)

实际代码测试及未完成验证见[专业能力验证记录](professional-validation.md)。
