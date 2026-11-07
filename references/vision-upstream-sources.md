# GitHub 视觉能力来源与拆解

日期 2026-11-07

摘要 按 GitHub 星数检索相关实现，再按图像、文字、空间关系及现有 CAD 流程的适用性选择。星数为本次查询快照。核心识别与缩放使用依赖包，组合规则在本项目技能入口加载。

## 候选比较

| 仓库 | 星数 | 与本任务的关系 | 本次采用 |
| --- | --- | --- | --- |
| anthropics/skills | 188344 | 官方 PDF Skill 含源文本读取、扫描页图像化 | 读取与 PDFium 渲染入口，文件级 Apache-2.0 |
| PaddlePaddle/PaddleOCR | 92396 | 本次 OCR 关键词检索中最高星的识别实现，含官方文字与文档解析 Skill | 文字、框坐标、分数、版面解析选路，Apache-2.0 |
| opendatalab/MinerU | 83258 | 整页文档转 Markdown/JSON | 候选记录，现阶段优先复用既有 PDF 路径 |
| tesseract-ocr/tesseract | 77402 | 通用 OCR 引擎 | 候选记录，本次采用 Paddle 系列模型 |
| docling-project/docling | 70246 | 文档版面、阅读顺序、表格、结构化输出 | 候选记录，适合后续复杂资料解析 |
| QwenLM/Qwen3-VL | 20175 | 官方目标定位、局部放大和空间关系示例 | 三类官方方法与坐标约定，Apache-2.0 |
| QwenLM/Qwen-Agent | 17257 | 官方图像放大工具实现 | 直接调用 image_zoom_in_qwen3vl，Apache-2.0 |
| RapidAI/RapidOCR | 8474 | PaddleOCR 模型的 ONNX 本地部署，支持 Windows | 本地 OCR 执行与原生 JSON 输出，Apache-2.0 |
| obss/sahi | 5591 | 已有检测模型的切片推理与结果合并 | 候选记录，接入前需要适用检测模型 |

检索使用 GitHub Repository Search 的 stars 降序，关键词包括 OCR、document parsing、agent-skills、image-understanding，并定向核实相关官方仓库。资料集合及无关高星项目按实际用途筛选。此表反映本次相关候选，准确率需结合具体样例验证。

## 固定来源与采用内容

### PaddleOCR 官方 Skills

固定提交 `dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf`。

- `paddleocr-text-recognition` 提供行级文字、检测框和识别分数的任务边界，平整图像可关闭方向分类及展平，异常需如实反馈。
- `paddleocr-doc-parsing` 提供表格、公式、多栏和复杂版面的结构化提取路径。
- 官方 Skill 的 CLI 示例使用云端 API。本项目保留该可选调用方式，并采用 RapidOCR 本地运行 PaddleOCR 模型完成文字识别。

[文字识别 Skill](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/skills/paddleocr-text-recognition/SKILL.md) · [文档解析 Skill](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/skills/paddleocr-doc-parsing/SKILL.md)

### Qwen 官方视觉工具与示例

Qwen3-VL 固定提交 `96588727e44c78b25ba03ea03b8e12f7e64fd0da`，Qwen-Agent 工具固定提交 `31a4d36d123688581a9e9744427272b33ce940e0`。

- `think_with_images` 采用观察、提出具体视觉问题、调用局部放大工具、查看返回图像再判断的循环。
- `2d_grounding` 采用对象边界框或关键点及属性的 JSON 输出，坐标范围为 0–1000。
- `spatial_understanding` 在对象定位后判断相对位置、可操作位置及空间关系。
- `ImageZoomInToolQwen3VL` 直接执行框坐标换算、裁剪和 smart_resize，结果继续交给当前宿主的图像查看工具。该调用只执行图像工具，Qwen3-VL 模型推理需另有对应模型服务。

[局部观察示例](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/cookbooks/think_with_images.ipynb) · [目标定位示例](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/cookbooks/2d_grounding.ipynb) · [空间理解示例](https://github.com/QwenLM/Qwen3-VL/blob/96588727e44c78b25ba03ea03b8e12f7e64fd0da/cookbooks/spatial_understanding.ipynb) · [图像工具源码](https://github.com/QwenLM/Qwen-Agent/blob/31a4d36d123688581a9e9744427272b33ce940e0/qwen_agent/tools/image_zoom_in_qwen3vl.py)

### RapidOCR 本地执行

源码审查提交 `a538d3a75e26ca7ac521da8602842b9d6e5a872d`，实测包 `rapidocr==3.9.2`、`onnxruntime==1.24.4`。运行配置采用依赖库默认 PP-OCRv6 small 检测与识别模型，以及 PP-OCRv4 文本方向分类模型。下载器按模型登记校验哈希。

采用上游 `RapidOCR()`、`engine(image)`、`result.to_json()`。输出含 `box`、`txt` 和 `score`，识别模型及后处理均由上游提供。

[官方用法](https://github.com/RapidAI/RapidOCR/blob/a538d3a75e26ca7ac521da8602842b9d6e5a872d/README.md) · [输出接口](https://github.com/RapidAI/RapidOCR/blob/a538d3a75e26ca7ac521da8602842b9d6e5a872d/python/rapidocr/utils/output.py) · [模型来源与许可](https://github.com/RapidAI/RapidOCR/blob/a538d3a75e26ca7ac521da8602842b9d6e5a872d/python/MODEL_LICENSES.md)

### Anthropic PDF Skill

固定提交 `2c5958ecac7cee2b583967a2c4981d0f4a75c579`。采用 `pypdf` 读取源文字及 `pypdfium2` 渲染页面的官方示例。仓库中的文件级许可证已实际核对为 Apache-2.0。

[PDF Skill](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/pdf/SKILL.md) · [PDFium 示例](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/pdf/reference.md) · [文件级许可](https://github.com/anthropics/skills/blob/2c5958ecac7cee2b583967a2c4981d0f4a75c579/skills/pdf/LICENSE.txt)

## 本项目组合方式

源文件 → 按格式读取/渲染 → 当前视觉模型定位目标与提出局部问题 → Qwen 官方工具放大 → Paddle 系列 OCR 补文字与坐标 → 当前模型核实形状和关系 → 现有 CAD 源清单及复绘检查。

本项目负责按 CAD 请求选择这些入口、记录来源和状态、交接已有清单。上游提示示例中的对象类别改为本次图纸实际对象。当前模型使用这些方法的效果、Qwen3-VL 模型表现及 OCR 表现需分别报告。

## 相关链接

- [组合后使用规则](image-reading.md)
- [许可与署名](vision-upstream-license.md)
- [实际测试记录](vision-upstream-validation.md)
