# 读图学习与工具应用记录

日期：2026-11-04

摘要：本轮实际阅读两篇原文、查看三张图，新增两条方法，并修复排布求解器忽略未支持约束的问题。资料数量、方法数量与工具验证分别记录。

## 实际读到的证据

| 原始资料 | 原文与图面观察 | 不能据此确定的内容 |
| --- | --- | --- |
| [RITCS / ATAMA](https://www.gooood.cn/en/erasmus-hogeschool-ritcs.htm)，原发布2026-11-03 | 原文涉及既有建筑改造、精确测绘和构件拆增；已看标高+0平面与AA剖面，观察到剖切标记、比例尺及不同高度空间的对应表达 | 没有从图片反推工程尺寸；缺图例时不将红/灰色自动定义为全部构件状态 |
| [ampm / 水形社](https://www.gooood.cn/en/ampm-outdoor-lifestyle-collective-by-inside-outside-studio.htm)，原发布2026-11-03 | 原文说明不规则角铺、可变展示和未来入口选项；已看带功能编号的平面，识别服务台、展示岛等图例与斜边边界 | 未来入口不是已确认现状；图中黑块的结构属性及通道尺寸仍须项目级证据 |

实际查看图像的[原始平面](https://oss.gooood.cn/uploads/2026/10/ritcs-p21-1350x882.jpg)、[原始剖面](https://oss.gooood.cn/uploads/2026/10/ritcs-p28-1350x419.jpg)和[ampm平面](https://oss.gooood.cn/uploads/2026/11/ampm-floor-plan-550x730.png)保留原作者权益。私有审阅记录保留原图哈希与查看时间，原图不进入发布包。

## 新增的决策方法

[现状与情景核对](learned/project-state-and-scenario-gates.md)将已确认现状、当前设计与未来选项分开，避免把文章中的未来设想自动变成当前改图指令。它增加状态和授权检查，补充原有“视图互证”方法。

[排布能力核对](learned/layout-geometry-capability-gates.md)要求先确认形状、固定障碍、保留通道及可移动对象，再选择工具。对尚不支持的几何约束明确拒绝，避免将外包矩形当成真实场地。

## 已应用到工具的修正

原求解器只读取width、height、clearance、items和obstacles，其他字段会被忽略；输入不规则boundary时可能仍返回矩形排布成功。0.1.1明确拒绝未支持的场地、物件旋转和障碍几何字段；仅对可表示的轴对齐矩形求解。

验证包括不规则边界与未映射保留区应拒绝、任意旋转应拒绝、显式矩形入口保留区应保持空置，以及真实MCP调用不能将未支持输入报为成功。用例位于tests/test_drawing.py与tests/test_mcp.py。结果不等于已具备任意多边形排布能力，也不替代消防、无障碍或运营设计审核。

## 相关链接

[Skill入口](../SKILL.md) · [方法索引](learned/index.md) · [研究流程](drawing-research.md) · [布局实现](../src/luomu_cad/optimizer.py)
