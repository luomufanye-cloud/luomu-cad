# 行业制图与标准学习要点

日期：2026-11-24

摘要：按行业整理Agent开工前应掌握的图纸组成、制图要点、设计复核项、常见错误和练习，并把每条要点挂到[标准索引](../standards-catalogue.json)里已查证的标准ID上。本目录只放原创归纳和官方阅读入口，不放标准或图集全文。

## 怎么用

1. 先查路线：`workbench_standards(operation="route", discipline="…")`。返回结果里的`learning_note`指向本目录对应文件。
2. 读本目录对应文件，掌握这类图纸“画什么、怎么画、容易错在哪”。
3. 需要具体数值或条文时，按标准记录的`source_url`去官方渠道阅读正文，记录条号/页码。本目录的归纳不能代替正文，也不能作为合规结论。
4. 交付前按[标准基础与交付依据](../standards-foundation.md)建立项目标准依据记录。

| 行业 | 路线ID | 学习要点 |
| --- | --- | --- |
| 机械制图 | mechanical | [mechanical.md](mechanical.md) |
| 产品设计（工业设计、家具、包装） | product | [product-design.md](product-design.md) |
| 空间设计（室内） | interior | [spatial-design.md](spatial-design.md) |
| 环境设计（室内外公共环境与导视） | environment_design | [environment-design.md](environment-design.md) |
| 景观设计 | landscape | [landscape.md](landscape.md) |
| 食品加工（厂房、车间与设备） | food_processing | [food-processing.md](food-processing.md) |

建筑、结构、机电、电力、水利、交通、船舶、服装等其他行业仍使用标准索引里原有的路线，尚无独立学习要点。

## 示例图纸

每篇要点配一张原创示例图纸（DXF，A3），由`scripts/build_learning_samples.py`生成，模型空间按实际尺寸（mm）绘制，图框和文字按出图比例换算。[示例索引](../../examples/learning-samples.json)记录每张图演示的要点、对应标准ID和示例自检结果。

| 行业 | 示例图纸 | 比例 |
| --- | --- | --- |
| 机械制图 | [阶梯轴零件图](../../examples/learning-mechanical-shaft.dxf) | 2:1 |
| 产品设计 | [路由器外壳外观尺寸图](../../examples/learning-product-enclosure.dxf) | 1:1 |
| 空间设计 | [卧室平面布置图](../../examples/learning-interior-bedroom.dxf) | 1:50 |
| 环境设计 | [广场导视点位图](../../examples/learning-environment-wayfinding.dxf) | 1:300 |
| 景观设计 | [场地竖向与种植设计图](../../examples/learning-landscape-grading.dxf) | 1:200 |
| 食品加工 | [面包坊车间工艺平面布置图](../../examples/learning-food-bakery.dxf) | 1:100 |

```text
python scripts/build_learning_samples.py check      # 重新生成并与仓库文件比对，同时跑几何质检
python scripts/build_learning_samples.py preview --output outputs/learning-previews
```

- 汉字用FangSong（simfang.ttf，宽度因子0.7，即长仿宋），尺寸数字用gbenor.shx与gbcbig.shx；本机缺这些字体时CAD会替换显示。
- 预览PNG由ezdxf离线渲染，“图”等个别汉字可能被涂成实心块，这是渲染器的填充问题，DXF在CAD中显示正常。
- 示例图纸只演示制图表达，不是工程、制造或报批图纸；自检只核对图中自身声明的内容。

## 内容的证据等级

每篇要点都区分三种来源，不混用：

| 标记 | 含义 | 能否当条文引用 |
| --- | --- | --- |
| 已读条文归纳 | 本轮实际读了官方全文对应章节，用自己的话归纳，并注明条号 | 只能作为“去哪条找”的指引，引用时仍以正文为准 |
| 教学归纳 | 按教材和行业通行做法整理，挂到候选标准上，未逐条对照正文 | 不能，只用于学习和自检 |
| 复核项 | 只列“要检查什么”，具体数值必须到正文查 | 不能，数值一律取正文 |

标准索引里每条记录的`evidence_level`说明了身份核实到什么程度：`official_metadata`为国家标准信息平台题录，`issuer_notice`为发布机关公告，`government_reprint`为政府网站转载的文本，`official_fulltext`为官方公开全文，`government_citation`表示未找到发布公告、只见政府公开文件引用，这类记录必须先向发布机关核实再采用。

## 合法阅读全文的入口

| 标准类型 | 官方入口 | 说明 |
| --- | --- | --- |
| 推荐性/强制性国家标准（GB、GB/T） | [国家标准全文公开系统](https://openstd.samr.gov.cn/) | 多数可在线阅读；采用国际标准的部分受版权限制，只能看题录 |
| 工程建设国家标准、通用规范（GB 50xxx、GB 55xxx） | 住建部公告页（索引里的`source_url`） | GB 55xxx通用规范在公告页附件公开全文；其余按公告说明到出版社取得 |
| 食品安全国家标准（GB 14881等） | 国家卫生健康委员会网站（索引里的`source_url`） | 官方公开全文PDF |
| 行业标准（JGJ、CJJ、QB/T等） | 发布部委公告、[行业标准信息服务平台](https://hbba.sacinfo.org.cn/) | 题录可查，正文多需正式出版物 |
| 国家建筑标准设计图集（如J、G系列） | 正式出版物 | 有版权，不进入公共仓库；项目需要时由使用者合法取得 |

不绕过登录和付费，不把私人取得的全文、客户图纸放进本仓库。

## 相关链接

[标准索引](../standards-catalogue.json) · [标准基础与交付依据](../standards-foundation.md) · [分专业绘图与实测验收](../professional-cad.md) · [Skill](../../SKILL.md)
