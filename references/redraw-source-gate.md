# 复绘源图清单与交付检查

日期：2026-11-06

摘要：使用源图清单、输出对象映射和绑定当前文件的对照记录共同检查复绘，防止生成结果与自生成预期相互印证。

## 从源图到输出

1. 绘制前固定源文件哈希、页码、视图范围及交付目标，完成源图对象清单。包括墙、门窗、家具设备、文字、尺寸、轴线、图名和比例。尺寸清单既包含总尺寸和外链，也包含所有内侧尺寸；识别困难的项目不能从清单删除。
2. 源清单记录可追溯的`source_locator`和模型坐标预期。转换原点、毫米比例及Y轴方向来自校准过程。坐标从源数据转换，不能从输出DXF回读后覆盖预期。可编辑语义无法确定的对象继续定位源界线、文字及关联构件；没有解决时只能保留进度，不能通过完整交付检查。
3. 生成脚本仅输出`reference_map`，把稳定的源对象ID对应到目标句柄。一个原生尺寸可对应源图中已识别的一组尺寸线、界线、箭头和数字；这一组必须先在源清单中定义。不能用宽矩形范围、中点、灰度或“数值相同”删除邻近图形。
4. 保存后运行完整检查，再实际对照全图与关键区域。发现问题保持源清单不变，修正转换或输出映射后重查。不得为了通过而把缺项标成不存在、增加宽泛容差或更改源尺寸。

## 完整命令

```text
python scripts/verify_redraw.py drawing.dxf mapping.json --reference-inventory source-inventory.json --source original.pdf --review review.json --report delivery.json
```

默认命令执行交付路径。缺少源清单、原文件或有效的对照记录均返回非零退出码。旧格式仅用于诊断时必须显式加`--structural-only`，其`complete_redraw_accepted`始终为false；不能拿诊断结果代替完整检查。

`mapping.json`示例：`{"reference_map":{"wall-1":"目标句柄","dim-1":"目标句柄"}}`。

源清单包含以下字段：

- `schema_version=1`、`source_sha256`、从0开始的`page`、`view`、DXF `units`、`delivery_target=offline_dxf/live_cad`。
- `review_regions`：至少包括`full_view`，并按源图列出文字密集区、内外尺寸、各门弧和关键节点等需要对照的区域ID。
- `objects`：每项有唯一`id`、`kind`、`source_locator`、正数`tolerance`、`expected`和`presentation`；模型坐标为三维毫米点。`presentation.linetype`声明源表达对应的实际线型名称，不能从目标图层反推。

`expected`按对象类型填写：

| kind | 预期字段 |
| --- | --- |
| LINE | start、end |
| ARC | center、radius、start_angle、end_angle；角度比较容差1e-6度 |
| CIRCLE | center、radius |
| SPLINE | degree、control_points、knots、可选weights |
| LWPOLYLINE | closed、points，每点为[x,y,bulge] |
| TEXT | text、at、height、rotation |
| DIMENSION | start、end、measurement、dimlfac、display_text、style、line_at；line_at为尺寸定义点defpoint，用于核对尺寸线所在位置 |

`style`支持复绘专题中的数值样式字段，并包括dimfxl和dimfxlon。映射遗漏、句柄重复占用、额外输出对象、类型错误、几何或线型不符、中文样式映射缺失及可疑损坏文字均拒绝。尚未支持的对象类型明确拒绝，不能拆掉后冒充已支持。源清单自身是否完整仍须对照原图，文件哈希不能代替这一判断。

## 对照记录

先调用检查得到`source_sha256`、`drawing_sha256`、`inventory_sha256`，然后针对这些文件实际查看并记录`review.json`：

- 三个哈希与检查结果一致；`reviewer`标明检查者或检查流程。
- `regions`覆盖清单中的每个区域；每项包含`reviewed=true`、具体`observations`、空的`unresolved`，以及`source`和`output`两份图片的`path`与`sha256`。相对路径以review.json所在目录为基准。
- `live_cad`还需`native_display`：`method=cad_mcp`、对应`drawing_sha256`、实际`document_token`和`preview`图片路径/哈希。只能使用已取得的MCP原生预览，不能用离线渲染冒充。

图片会检查存在、哈希和可读取性；软件不能判断检查者是否真的理解图纸。因此只能在真实查看后填写观察，不自动生成“全部正常”记录。记录过期、问题未解决或缺少任一区域即拒绝。成功表示已声明源清单的对照和记录要求通过，不是工程规范认证。

## 坐标与曲线工具

`luomu_cad.reference_geometry.PageTransform(mm_per_unit, origin, flip_y=True)`提供统一缩放和显式Y镜像。`point()`转换点；`arc()`转换已确认的圆弧中心、半径和角度，镜像时反转弧向。不能仅转换圆心而保留原来的起止角。

PDF中的三次Bezier不一定是精确圆弧。`add_cubic(modelspace, four_controls, dxfattribs)`将四个控制点转换为可编辑的三次SPLINE，保持曲线而不固定采样。只有已经确认的解析圆弧才使用arc；需要拟合时另行计算源曲线与拟合结果的误差上界。

线型以源路径dash信息及明确对象语义为依据；连续线保留连续。灰色、细线不等于轴线，尺寸界线也不等于轴线。不随意把源线统一改成CENTER，更不能以修改线型掩盖转换中产生的长线。

中文新样式使用`configure_cjk_style`同时设置字体文件和字体族；其检查已接入复绘验收，无需依赖额外脚本是否被模型记住。原文已损坏时只能从源图恢复；字体正确与目标CAD原生显示仍是不同检查项。

## 相关链接

[忠实复绘方法](faithful-redraw.md) · [中文与尺寸界线](text-and-dimensions.md) · [ezdxf ARC方向定义](https://ezdxf.readthedocs.io/en/stable/dxfentities/arc.html) · [ezdxf SPLINE控制点与节点](https://ezdxf.readthedocs.io/en/stable/dxfentities/spline.html)

软件资料检索日期：2026-11-06。
