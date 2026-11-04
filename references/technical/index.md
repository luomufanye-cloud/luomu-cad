# 节点、工法与专业系统知识

日期：2026-11-04

摘要：技术卡保存实际研读的构造与系统内容，并附版本、出处、适用条件和练习。当前为首批主题，未覆盖全部施工图专业。

| 技术卡 | 已学习的内容 | 当前状态 |
| --- | --- | --- |
| [厨卫防水交界](wet-area-waterproof-interfaces.json) | 管根、地漏、转角的处理与增强；涂层、养护、试验和保护的先后；产品配比及厚度资料的条件记录 | studied；工序和条件练习另有结果，不等于项目施工通过 |
| [接地系统拓扑](earthing-system-topology.json) | TT/TN/IT示意、N/PE/PEN功能及分合区段；指定TN-S下游端子的识图练习 | studied；尚未完成保护选择和设计计算 |
| [墙地防水连续性原理训练](wall-floor-waterproof-continuity.json) | 原生线/圆弧示意绘制、保存后端点回读、断点和缺失上翻错误题 | exercise_checked，仅限无工程单位的示意；工程节点尺寸和构造验收未完成 |
| [四管制风盘接口识读](four-pipe-fan-coil-interfaces.json) | 区分冷却与加热盘管进出水、冷凝水出口和电气盒；区分公称螺纹与实际管径 | studied；完成接口问答与条件错题，安装、毫米尺寸复绘和系统设计待续 |

使用workbench_technical的list/get读取；record记录审阅后的卡；check_sequence检查卡中明确的工序先后；check_applicability列出缺少或不匹配的项目条件；check_connections只检查卡中明示的训练端子与区段。所有练习均返回engineering_approval=false。

check_applicability把空值、空容器、空白文字及明确的missing/unknown/unconfirmed/pending/tbd、待核实/待确认/未确认/缺失/待补充视为未提供条件。它仍只检查必需输入是否提供和明示的匹配条件，不验证输入真实性或工程完整性；填了字符串不能视为计算已通过。

## 相关链接

[学习与考核范围](../professional-learning.md) · [首批实际记录](../technical-study-2026-11-04.md) · [连续性训练记录](../waterproof-training-2026-11-04.md) · [研究流程](../drawing-research.md)
