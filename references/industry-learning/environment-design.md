# 环境设计学习要点（室内外公共环境与导视）

日期：2026-11-24

摘要：环境设计在国内院校通常涵盖室内、景观和公共空间（含导视系统）。本路线把这几类标准串起来，重点补充导视系统和室内外衔接。本页为**教学归纳**和**复核项**。路线：`workbench_standards(operation="route", discipline="environment_design")`；具体交付物再回到`interior`、`landscape`或`building_architecture`路线。

## 先判断交付物属于哪一类

| 交付物 | 主路线 | 学习要点 |
| --- | --- | --- |
| 室内空间 | interior | [spatial-design.md](spatial-design.md) |
| 场地、广场、公园、居住区环境 | landscape | [landscape.md](landscape.md) |
| 公共建筑外环境与建筑本体 | building_architecture | — |
| 导视系统 | environment_design | 本页 |

## 一套环境设计图纸包含什么

| 图纸 | 内容 |
| --- | --- |
| 总平面/场地平面 | 坐标、标高、用地边界、出入口、与建筑关系（总图约定见`site-plan-drawing`） |
| 功能分区与流线分析 | 人行、车行、无障碍和后勤流线，以及流线上的决策点 |
| 竖向与铺装 | 室内外高差衔接、排水坡向、铺装材料与拼缝 |
| 设施与小品详图 | 座椅、构筑物、景观照明灯具定位 |
| 导视系统 | 点位图、牌体分类与立面、版面（文字、图形符号、箭头、颜色）、安装详图 |

## 导视系统要点

| 主题 | 要点（教学归纳） | 候选标准ID |
| --- | --- | --- |
| 设置原则 | 导视点位跟随流线布置，在出入口和每个需要选择方向的决策点设置；信息从总到分保持连续，同一目的地在整条路径上名称一致 | `wayfinding-setting` |
| 导向要素设计 | 箭头、图形符号、文字和颜色组合的规则；设置高度、视距与字高的关系按正文 | `wayfinding-elements` |
| 图形符号 | 优先采用国家标准中的通用公共信息图形符号，不自绘含义相同的变体 | `public-symbols` |
| 无障碍 | 盲道、无障碍出入口和无障碍设施的标识与室内外连续 | `accessibility` |

官方目录显示GB/T 15566.1-2007、GB/T 20501.1-2006、GB/T 10001.1-2012均已废止，引用时用索引中的现行版本。

## 设计复核项

| 复核什么 | 候选标准ID |
| --- | --- |
| 室内外无障碍通行连续、坡道和高差处理 | `accessibility` |
| 公共空间的民用建筑通用要求、装修防火 | `civil-building-code` `interior-fire` |
| 声、光、热环境和照明 | `building-environment` `lighting` |
| 公园、绿地和居住区环境 | `park-design` `landscape-project-code` `residential-planning` |
| 人体尺寸（座椅、柜台、扶手） | `body-dimensions-adult` |

## 常见错误自检

1. 导视点位与流线决策点不对应，转弯处缺指引。
2. 同一目的地在不同牌面上名称不一致。
3. 自绘图形符号，与国家标准通用符号含义冲突。
4. 室内外高差处没有无障碍坡道或缘石坡道。
5. 总图坐标、标高单位混用。

## 在本Skill中练习

- 专业模板：`workbench_professional(profile_ids=["space", "exterior", "commercial"])`；图种合同：`workbench_industry`的`space.zoning`、`space.circulation`、`exterior.site`。

**练习（原创题）**：在一个有两个出入口的小型广场上设计导视系统。要求：画出人行主流线并标出所有决策点；每个决策点布置一个导视牌并编号；做点位表（编号、位置、牌型、指向的目的地）；检查同一目的地名称是否一致；到GB/T 10001.1-2023正文中找到所用图形符号的编号，记进标准依据记录。

## 示例图纸

[广场导视点位图](../../examples/learning-environment-wayfinding.dxf)（A3，1:300）是上面练习题的一种参考做法：先画人行流线和决策点D1～D3，入口设总览牌，每个决策点设方向牌，设施处设名称牌，点位表与图面编号一一对应，目的地名称统一。图形符号以文字代替，牌体尺寸和字高不给数值。示例自检结果见[示例索引](../../examples/learning-samples.json)，预览与复核方法见[索引页](index.md#示例图纸)。

## 边界

导视牌体的结构安全、照明电气和户外广告管理另有依据；本页不提供字高、视距等数值。

[返回索引](index.md)
