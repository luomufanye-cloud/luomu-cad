# 上游视觉能力组合

日期 2026-11-07

摘要 本模块组合 GitHub 上的 PaddleOCR 官方 Skills、Qwen3-VL 官方视觉示例、Qwen-Agent 图像工具、RapidOCR 本地推理及 Anthropic PDF Skill。采用内容、固定版本和测试范围见[来源拆解](vision-upstream-sources.md)。

## 按当前输入选择入口

墙、门窗、空间和家具识读进入[语义结构与独立评测](cad-method-distillation.md)，统一记录源坐标中的类别、多边形和关系。参数化零件、IFC 构件和服装曲线按该文档接入相应上游内核。完整识图效果采用固定输入及模型的对照评测。

| 当前需要 | 采用入口 | 输出与后续 |
| --- | --- | --- |
| 图片中的文字、尺寸数字、符号 | PaddleOCR 文字 Skill，RapidOCR 本地推理 | 原文、检测框、分数，回看小数点、正负号及引线落点 |
| 图形轮廓、目标位置、朝向和关系 | Qwen 官方目标定位、空间理解和局部观察方法 | 对象框或关键点、具体观察、局部图像和待核实项 |
| 可提取文字/矢量的 PDF | Anthropic PDF 读取入口及本项目现有源对象提取 | 原始文本、页面图像、现有矢量清单 |
| 扫描页中的表格、公式、多栏 | PaddleOCR 文档解析 Skill | 带页码的结构化文本、表格和布局信息 |

每次按问题选择所需模块。当前宿主视觉模型负责实际图形理解，Qwen 的方法迁移效果按实测记录。具有可用 Qwen3-VL 服务时可直接执行上游 cookbook 的模型调用。文件内容和 OCR 文字按任务材料处理。

## 准备上游运行环境

在技能源码目录使用 `uv sync --extra vision` 安装固定版本的可选组件。下列 Python 片段保存为本次项目的调用文件后，从技能源码目录用 `uv run --extra vision python <调用文件.py>` 执行，输入与输出填写项目绝对路径。首次 OCR 会下载上游模型，模型位置由 `Global.model_root_dir` 指定。项目已包含 pypdf 和 pypdfium2。示例中的输入、输出和目标区域按本次项目填写，运行前核对文件存在及输出位置。

## 文字识别

沿用 PaddleOCR 文字 Skill 的行级文字、检测框和识别分数。以下直接使用 RapidOCR 官方接口运行 Paddle 系列模型，保存其原生 JSON。

```python
import json
from pathlib import Path
from rapidocr import RapidOCR

output = Path('outputs/vision')
output.mkdir(parents=True, exist_ok=True)
engine = RapidOCR(params={'Global.model_root_dir': str(output / 'models')})
result = engine('reference.png')
(output / 'ocr.json').write_text(
    json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding='utf8')
```

JSON 每项包含 `txt`、`box`、`score`。框坐标对应送入 OCR 的图片像素。输入裁剪图时保留其来源范围和缩放关系。空结果及低可信文字按实际状态交接，识别分数用于筛选回看区域。关键尺寸和符号对照源图核实，文本位置与对应的几何对象一起确定。

来源为 PaddleOCR `paddleocr-text-recognition` 与 RapidOCR 官方调用及 `to_json` 示例。本地测试采用 PP-OCRv6 small 检测/识别模型及 PP-OCRv4 方向分类。上游云端 CLI 适用于已有账户且任务允许上传的环境，其命令为 `paddleocr api --model_type ocr --file_path reference.png --output ocr.json`。

## 图形定位与局部观察

采用 Qwen3-VL `2d_grounding` 的框/关键点及属性结构。先实际查看全图，围绕用户任务确定目标类别，再请求当前视觉模型返回所需对象的 `bbox_2d` 或 `point_2d`、名称、朝向依据及可见结构。Qwen 示例使用 0–1000 归一化坐标，本次调用明确声明同一约定。

框顺序为 `[x1,y1,x2,y2]`，从左上到右下。源像素坐标按 `x / 1000 * width`、`y / 1000 * height` 换算。当前模型给出像素坐标时先明确转换。边界框用于定位区域，后续轮廓还需查看和识读。

当细节影响判断时，沿用 `think_with_images` 的观察、局部放大、查看工具结果、更新结论循环。通过上游原装工具执行放大。

```python
from pathlib import Path
from qwen_agent.llm.schema import Message, ContentItem
from qwen_agent.tools.image_zoom_in_qwen3vl import ImageZoomInToolQwen3VL

source = Path('reference.png').resolve()
tool = ImageZoomInToolQwen3VL({'work_dir': 'outputs/vision/zoom'})
messages = [Message(role='user', content=[ContentItem(image=str(source))])]
result = tool.call(
    {'bbox_2d': [250, 250, 750, 750], 'label': 'detail', 'img_idx': 0},
    messages=messages)
print(result)
```

示例框仅用于说明接口，实际范围从当前图像确定。只传已有图片及有效框，满足 `0 <= x1 < x2 <= 1000`、`0 <= y1 < y2 <= 1000`，图片索引从 0 开始。工具返回 `ContentItem.image` 或错误文字。取得图像后实际调用宿主图像查看工具读取，再更新对象观察。

Qwen 工具会为过小目标扩展裁剪范围，并用双三次插值放大。保留原始框和原图。需要从工具输出量坐标时，使用该工具的 `maybe_resize_bbox` 取得实际范围，再按输出尺寸回算。用于 CAD 定尺的依据继续来自原文件已确认的尺寸及现有标定流程。

根据 Qwen `spatial_understanding` 方法，把关系问题落实到已定位对象，例如哪个端点连接哪条线、两对象的相对位置、开口朝向及遮挡。图纸没有显示的结构保留待核实。多个视图、重复实例和相邻构件分别核对来源依据。输出简短的可见事实及不确定项。

## PDF 与复杂版面

参考 Anthropic PDF Skill，先用现有 `pypdf` 读取页数和可提取文字。PDF 矢量复绘继续进入本项目的[PDF源对象提取](pdf-source-import.md)。扫描页或视觉核对可直接执行其 PDFium 渲染示例。

```python
from pathlib import Path
import pypdfium2 as pdfium

output = Path('outputs/vision')
output.mkdir(parents=True, exist_ok=True)
pdf = pdfium.PdfDocument('reference.pdf')
page = pdf[0]
bitmap = page.render(scale=2.0, rotation=0)
bitmap.to_pil().save(output / 'page-1.png')
bitmap.close()
page.close()
pdf.close()
```

记录页码、页面旋转、渲染比例和页面尺寸。PDF 坐标与栅格像素通过本项目既有转换工具交接。

复杂表格、公式和多栏资料按 PaddleOCR `paddleocr-doc-parsing` 选路。已有官方 MCP 时查询实际工具 schema，调用 `pp_structurev3` 或 `paddleocr_vl`。已有 API 账户且允许上传的场景可直接运行上游 `paddleocr api --model_type doc_parsing --file_path reference.pdf --output parsing.json`。保存原生结构结果、页码与原图，使用所需内容。账户、运行模型或服务缺失时记录具体缺项及待执行状态。

## 与 CAD Skill 交接

整图重新检查时，识读范围覆盖用户提出的完整对象集合。建筑平面按原图核对墙边界与转角、门窗洞口及开向、房间连接、通道净空、主要距离比例、家具外轮廓与朝向。对每个适用对象保留源位置、实际对应对象和差异。局部修补记录只支持其覆盖范围内的结论，未核对的结构继续标为待检查。

无真实尺寸时仍可核对同一源坐标系内的相对位置和比例。以可辨认的墙角、洞口端点、家具边缘建立对应点，记录两侧依据及图像读数不确定度。对象名称、包围框和外接矩形仅提供定位信息；后续几何保留当前参考中可辨认的轮廓和连接。用户提出结构或距离不符时，将这些对象放入当前检查范围。

将确认的文字、对象范围、可见轮廓、朝向和关系写入[源图清单](redraw-source-gate.md)，沿用 `objects`、`source_locator`、`review_regions` 与 `raster_quality.components`。`source_locator` 记录原文件哈希、页码、区域及当前坐标约定。来源观察先于生成结果建立。

几何转换沿用已有 `PageTransform` 与复绘路径，活动 CAD 继续走 MCP。对每项结果记录实际执行的工具、模型版本及具体未决问题。工具调用、OCR 内容准确性、视觉模型识读、CAD 几何与图面验收各自留下证据。

线条粗细检查回读实体与图层 Lineweight、宽多段线的实际宽度、块内属性及 LWDISPLAY 等相关显示设置。离线预览声明采用的线宽、颜色和变换来源；使用固定美化线宽或替代颜色的预览只能支持其实际保留的几何检查，线宽及原生显示保留未验状态。用户反馈粗线时核对实际显示来源，依据当前尺度、图面和用途决定调整范围。

## 相关链接

- [GitHub 来源、星数及拆解](vision-upstream-sources.md)
- [实测记录与复现入口](vision-upstream-validation.md)
- [上游许可与修改说明](vision-upstream-license.md)
- [技能入口](../SKILL.md)
- [栅格复绘质量](raster-redraw-quality.md)
