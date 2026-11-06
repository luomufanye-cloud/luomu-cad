# 模型调用流程与平面交付检查

日期：2026-11-06

摘要：不同Agent与模型使用同一任务契约、工具Schema和可复核结果。工具成功、图纸可打开、设计要求完成是不同检查项。

## 确认实际执行版本

文件任务开始运行`python scripts/preflight.py --mode offline --require-version <当前pyproject版本>`，记录identity中的Skill根目录、source_version、runtime_version、runtime_module及checker_sha256。源码更新不代表非editable环境和旧MCP进程已经更新。版本不一致时先按安装说明更新对应环境，重建随包MCP进程并重新读取Skill；不能只看文件夹版本号。检查器报告必须属于当前文件及当前版本；命令失败时不得复用上一轮PASS。

## 绘制前固定任务

从当前要求提取交付目标，不以生成器示例代替：

| 条件 | 执行选择 |
| --- | --- |
| 在已运行AutoCAD中绘制、编辑活动DWG | `task_target=live_cad`，先列文档、连接并回读；不能静默改成离线DXF。 |
| 明确要生成离线DXF文件 | `task_target=offline_dxf`，再选择基础几何或带家具平面。 |
| 按参考图复绘 | deliverable=faithful_redraw，先按[复绘契约](faithful-redraw.md)及[独立源清单](redraw-source-gate.md)定尺、登记对象；不得为了工具能力更改门位、墙体或设计。 |
| 新设计平面 | 先确定房间功能、面积口径、入口、动线、家具与设备、门窗、尺寸和图幅，再组织参数。 |

调用`cad_adapt_session`时传入真实披露的模型标识及`task_target`、`deliverable`；身份未知保留unknown。返回下一步工具与输入要求。模型名称不改变几何、权限和验收标准，不假定模型记得上轮工具结果。每阶段保存简短任务状态：目标、当前文件、已通过项、失败项及下一步。

当前随包CAD适配器只附着已运行实例，不提供启动AutoCAD的工具。连接失败时检查返回的原始错误和运行环境；不能声称已启动，也不能把离线文件当成活动CAD任务完成。恢复规则见[使用说明](usage.md)。离线生成器的`target=live_cad`会明确返回`TARGET_MISMATCH`。

## 图纸内容与设计关系

1. **功能与面积**：核对房间数量、功能、分区及相互联系。建筑外包面积、室内净面积、阳台面积分别计算；表格合计需重新求和，不凭文字报告判断面积符合。
2. **入口与动线**：从入口依次走到公共区、各房间及阳台，检查门扇开启、家具和必要通行空间。通行宽度采用明确的设计条件，涉及规范时补相应依据。厨房、卫生间须布置所需设备并检查使用空间。
3. **家具与门窗**：尺寸和位置显式提供。新设计使用自定条件时标明其性质；复绘按原图。不能因某种门扇画法受限而移动入户门。先用`hand`确定铰点，再用`swing_side`确定开启侧；推拉门使用`sliding_door`，不能登记成窗。
4. **标注与比例**：模型为毫米；纸面尺寸字高随比例一次换算，默认纸面3.5毫米是本项目显示设置，不是所有工程的统一要求。校核实际定义点、原生测量和字形方向。外包、轴线、洞口分段分别表达，量主体时显式选择主体墙，阳台只影响尺寸线避让位置。
5. **交付范围**：按要求核对家具设备、墙体、门窗、房名、尺寸链、表格与图框。`geometry_plan`输出不能直接称作带家具平面；平面布置也不能自动代替全部施工图专业内容。

## 可用输入

自由设计家具先按[家具关系与使用空间](furniture-placement.md)确定靠墙或独立布置及使用条件。每件家具必须声明placement、clearances、clearance_basis及room；不能只给任意坐标。

`workbench_generate`支持`target=offline_dxf`。`spec.deliverable`包括：

- `geometry_plan`：基础墙体、开口等几何图；返回实际家具数量和有限检查范围。
- `furnished_plan`：必须提供`floor_boundary`、`furniture`、逐房间`furniture_requirements`和`clear_zones`。缺项或碰撞时拒绝生成，不能静默忽略家具。

家具采用独立可编辑INSERT。`kind`支持bed、sofa、table、chair、cabinet、sink、toilet、shower、hob、fridge；均为本项目绘制的二维简化符号，不是厂商产品模型。`at`为未旋转矩形的左下点；`width/depth`为实际毫米，`rotation`绕该点逆时针旋转，`room`绑定房间ID。

```json
{
  "id":"bed-1", "kind":"bed", "room":"R2",
  "at":[6500,3875], "width":1800, "depth":2000, "rotation":0,
  "placement":{"mode":"wall","wall":"EXT","gap":0},
  "clearances":{"front":600,"left":600,"right":500},
  "clearance_basis":"模拟练习毫米输入，适用墙面Y=5875"
}
```

房间配置示例为`{"R1":["sofa"],"R2":["bed"]}`，只说明本例要求；真实任务需按功能列齐。通道示例为`{"id":"passage","at":[3500,1500],"width":900,"depth":3000}`，数值均为示例设计条件。验证家具与墙体、家具之间、门扇扫过区、预留通道及所属房间的几何关系；门扇扫过区按三度采样并外扩半毫米用于本工具碰撞筛查，不能代替精确施工间隙校核。

`floor_boundary`独立定义室内计算边界，无需添加重复的闭合假墙。`chains.wall_ids`选择测量范围；`levels`可为`openings/axes/overall`。轴线层须提供`axis_x/axis_y`的明确坐标，不能从所有墙线猜轴线。`sides`支持bottom/left/top/right。标注位置仍须看图检查；洞口可提供`dimension_offset`和`tag_at`进行局部排版调整。

开口`hand=left/right`选择沿墙方向的起点/终点作为铰点；`swing_side=left/right`选择墙方向左侧/右侧开启。两者独立，不改变洞口位置。修改开向后重新检查门扇、家具和通道。

## 错误与验收

MCP错误保留原始文字和`error_type`。数值、洞口重叠、缺家具等输入错误先修参数，不无限重试，不绕开服务直接写活动CAD。两个独立洞口之间不足一毫米仍按当前几何约束拒绝；此阈值不是承重墙垛的设计依据，连续组合洞口须另作明确构件设计。

验收按任务逐项进行：实际保存文件回读；家具数量、范围和旋转；门窗开口及原生尺寸；纸面字高与图框比例；整图与密集区视觉检查；功能、动线及专业条件。`ok=true`只覆盖返回报告声明的机器检查，`full_construction_delivery_accepted=false`不得改写成完整设计通过。

回归使用原创合成输入与实际失败条件验证接口，不等同于某个宿主或模型的完整使用验收。具体模型只有实际完成“理解任务—选择路径—调用—检查—纠错”的运行记录后，才能记为实测覆盖。

## 相关链接

[Skill入口](../SKILL.md) · [中文与尺寸界线](text-and-dimensions.md) · [源图核对](cad-source-intake.md) · [MCP与安装](usage.md)
