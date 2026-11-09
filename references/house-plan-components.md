# Luomu CAD 构件库与门墙连接

日期：2026-11-09

摘要：Luomu CAD 构件库提供二维组件、门窗目录、墙体切洞和墙角连接功能。适用于直墙平面图的参数化构件生成。组件选择、尺寸、位置和朝向需要来自源图识读记录。

## 调用入口

先查询所需类别，再按源图选择匹配组件。MCP 工具为 `workbench_components`，支持 `catalogue` 和 `build`。CLI 提供相同生成实现。

```text
python scripts/build_components.py catalogue --query 沙发
python scripts/build_components.py build --spec examples/house-components.json --output runtime/components/example-01
```

输入格式见 [可执行示例](../examples/house-components.json)。输出包含原生 DXF、`native-geometry.json` 和 `component-report.json`。现有输出目录内已有 `components.dxf` 时要求改用新目录，避免覆盖基线。

活动 AutoCAD 任务由现有 CAD MCP 服务读取原生几何并写入当前图纸，再回读实体。组件生成本身在离线运行，输出 JSON 坐标单位为 `library_mm`，写入时乘 `drawing_units_per_library_mm`。最终用户交付继续遵循其保存和出图要求。

## 门墙模型

- 墙体采用节点引用、轴线和厚度。共享转角使用相同节点 ID。
- 每个门窗明确 `wall` 宿主、沿墙起点的距离 `pos`、洞口净宽 `width`、`side` 与 `hinge`。
- `side=1` 表示沿墙 a→b 的左侧，`side=-1` 表示右侧。单开门 `hinge=false` 铰点在洞口沿轴线较小坐标端，`hinge=true` 在另一端。输出坐标采用 CAD 的 Y 向上约定。
- 洞口先切墙，再从同一洞口边界构造门扇和开启弧。单开门开启弧半径等于洞口宽，开启门扇与墙轴垂直。默认门扇厚度为 40 mm，源坐标模式按库比例缩放。
- 原图采用其他开启角度、特殊门框或门扇厚度时，当前单开门组件需要扩展相应参数并验证后使用。图库参数不可覆盖源图明确的表达。
- 重叠洞口、越过墙端的洞口、墙角侵入洞口、缺少宿主或开向的输入会返回错误。新增墙穿越已有洞口也会被几何检查拦截。
- 飘窗和车库门依赖墙体的明确 `exterior_side`，外侧取值与 `side` 相同。

`units=mm` 输入真实毫米。仅有无尺寸图片时使用 `units=source`，提供 `library_scale` 和 `scale_basis`，前者表示每库毫米对应多少源图坐标单位，后者记录符号缩放依据。此模式保留 DXF units=0。家具尺寸字段随比例换算，家具 `opt`、`cab`、`kit` 高级参数沿用组件库毫米约定。

## 图库范围

构件库由 luomufanye-cloud 编写，提供 14 类门窗与 317 个目录标识。全部条目可生成原生几何，导出后回读检查。默认尺寸为可编辑参数，实际复绘按源图已确认尺寸填写。构件采用参数化轮廓和线稿表达。

符号按类别构造床枕、座垫、靠背、柜格、洁具轮廓、设备格栅等局部结构。线稿样式由本项目设计；自由轮廓、曲线座椅路径及柜格配置使用明确输入。复绘时根据当前源图选择或扩展对应形状。

部分自由造型本来就采用平面投影简图。条目存在只说明该图形可生成。复绘时仍需对照源图扶手、靠背、座面、洁具轮廓及开向，选择匹配条目或扩展实际几何。

圆弧、圆和椭圆保留原生曲线，二次和三次贝塞尔写为相应次数的控制点 SPLINE。已离散的曲线按组件定义路径保留。填充颜色映射为轮廓表达；本入口输出二维线稿，材质、贴图和文字排版按任务另作处理与对照。默认图层线重为墙 0.25、门窗 0.13、家具 0.09 mm，可编辑 DXF 的多段线几何宽度为零。

2026-11-08 更新：输入 `opening_layer_mode=by_type` 时，平开窗、推拉窗、落地窗、高窗、飘窗和玻璃幕墙使用 `A-WINDOW`，门和垭口使用 `A-DOOR`。原有输入未指定模式时，门窗继续使用 `A-DOOR`。可用 `lineweights_mm` 为 `wall`、`door`、`window`、`furniture` 分别提供本次所选毫米线重，例如 `{"door":0.18,"window":0.09}`。分开线重需采用 `by_type`。仅接受 DXF 标准可表示的线重值，无法表示的值返回错误，不静默取近似值。

生成后通过独立样式检查器回读每个实体的有效线重、线型以及多段线整体宽度和各顶点宽度，并验证组件与图层映射。`style_readback` 记录实际检查范围，`plot_style_verified=false` 表示 CTB/STB 和出图结果仍需按当前项目验证。线重属于纸面表达，多段线宽度属于模型几何，两者分别检查。默认值为示例，并非所有专业强制标准。[AutoCAD 线重说明](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-4B33ACD3-F6DD-4CB5-8C55-D6D0D7130905.htm) · [ezdxf 图形属性文档](https://ezdxf.readthedocs.io/en/stable/tutorials/common_graphical_attributes.html)

## 实际生成与验证

生成后检查洞口范围墙体重叠面积、铰点侧洞口边界连接、保存后的墙体轮廓，以及单开门的圆弧中心、半径、门扇方向和门扇端点。报告将 `reference_similarity_verified` 保持为 false，直至另有独立源图对照。

重新生成任务必须检查旧几何是否已满足当前源图。旧版实体复制脚本、历史回读 JSON 或家具圆角补丁无法承担门墙结构重建。先重建出错构件的宿主和洞口关系，生成一个代表组件并回读验证，再扩展到重复实例。

组件库提供参数化绘制函数。图片识读由当前视觉模型完成，并通过独立源图对照检查对象、轮廓与位置。

## 组件版本与许可

构件执行代码与新参数化线稿由 luomufanye-cloud 维护，适用本项目 MIT 许可；实现位置及目录摘要见[构件库记录](house-plan-components-source.json)。底层几何、DXF 等库按各自依赖许可安装。Python 构件入口不再要求 Node；原 Node 调用入口作为兼容接口保留。
