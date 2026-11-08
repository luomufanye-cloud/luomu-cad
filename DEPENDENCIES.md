# 依赖与资料来源

日期：2026-11-07

摘要：项目自有实现与外部库、设计资料分别管理。使用开源基础库是本项目的依赖关系，不表示库代码是本项目原创；安装依赖时仍须遵守其各自许可。

| 包 | 用途 | 依赖许可 |
| --- | --- | --- |
| mcp | stdio服务协议与客户端 | MIT |
| ezdxf | DXF格式读写及离线渲染 | MIT |
| Shapely | 平面几何运算 | BSD-3-Clause；GEOS按自身许可 |
| OR-Tools | 整数约束求解 | Apache-2.0 |
| matplotlib | 保存离线预览 | PSF-based，详见distribution metadata |
| fontTools | 读取实际字体字形与字符覆盖 | MIT |
| Pillow | 图像基础支持 | MIT-CMU |
| pypdfium2 / PDFium | 本地PDF路径、字形和源页读取 | pypdfium2为Apache-2.0或BSD-3-Clause；PDFium为BSD风格并保留其捆绑组件通知 |
| pypdf | PDF内容流与图形状态预检 | BSD-3-Clause |
| Scrapling | 公开HTML选择器 | BSD-3-Clause |
| HTTPX / Protego | 有限HTTP请求 / robots解析 | BSD-3-Clause |
| pywin32 | Windows服务端ActiveX访问 | PSF-2.0 |
| RapidOCR / ONNX Runtime（vision 可选依赖） | 直接运行 PaddleOCR 模型，返回文字、框坐标和分数 | Apache-2.0 / MIT，模型权重遵循许可声明 |
| Qwen-Agent / SoundFile（vision 可选依赖） | 官方局部放大工具及其导入依赖 | Apache-2.0 / BSD-3-Clause，捆绑库依各自许可 |
| CadQuery（独立可选运行时） | 参数化 BRep、STEP 导出重读、投影 | Apache-2.0；OCP/OpenCascade 等传递组件保留各自许可 |
| 三维实体验收运行时（独立可选） | 实体建模、特征量测、四视图与精确差异检查 | [依赖名称、版本及许可](THIRD_PARTY_NOTICES.md#optional-solid-model-runtime)，安装版本见独立锁定文件 |
| IfcOpenShell（独立可选运行时） | IFC 关系、几何及格式检查 | LGPL-3.0，组件通知保留在安装包 |
| FreeSewing（独立 npm 运行时） | 参数化量体纸样设计及曲线 | MIT，依赖保留各自许可 |

CAD 论文方法与运行时来源见[技术拆解](references/cad-method-distillation.md)及[固定来源](references/cad-upstream-sources.json)。本项目新增接口适配、评测与测试，原装内核通过包管理器安装。源码包包含适配代码与依赖锁定记录。神经网络训练与权重蒸馏尚未执行。

实体检查的实际调用和部署条件见[三维实体验收](references/solid-model-review.md)及 `references/solid-runtime-lock.json`。该运行时使用单独环境，避免 OCP 版本与现有 CadQuery 环境冲突；源码包不包含该运行时依赖的源码及二进制。来源信息集中在[第三方声明](THIRD_PARTY_NOTICES.md)。

视觉模块的选型、固定提交、实际采用的参考内容见[来源拆解](references/vision-upstream-sources.md)。引用的 Skill 与示例保留[第三方署名及 Apache-2.0 许可](references/vision-upstream-license.md)。可选依赖通过 `uv sync --extra vision` 安装。识别模型在首次执行时从模型发布地址下载，运行缓存位于所选项目目录。

确切版本与传递依赖见uv.lock；包的许可证、NOTICE和版权记录保留在安装环境的distribution metadata。仓库与源码ZIP不打包上述包的源码或二进制。若以后制作包含依赖的可执行文件，需要同时提供对应通知。

资料平台的项目图纸、图片、文字与厂家文档仍由各自作者或权利人持有；仅记录可追溯链接与短索引，不将其标为本项目原创。references/learned中的内容为本项目自行归纳的工作方法，保留来源与适用边界。

## 相关链接

[MIT说明](https://opensource.org/license/mit) · [GitHub开源许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) · [ezdxf](https://github.com/mozman/ezdxf) · [Shapely](https://github.com/shapely/shapely) · [OR-Tools](https://github.com/google/or-tools) · [Scrapling](https://github.com/D4Vinci/Scrapling)
