# 依赖与资料来源

日期：2026-11-07

摘要：项目自有实现与外部库、设计资料分别管理。使用开源基础库是本项目的依赖关系，不表示库代码是本项目原创；安装依赖时仍须遵守其各自许可。

| 包 | 用途 | 上游许可 |
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

确切版本与传递依赖见uv.lock；包的许可证、NOTICE和版权记录保留在安装环境的distribution metadata。仓库与源码ZIP不打包上述包的源码或二进制。若以后制作包含依赖的可执行文件，需要同时提供对应通知。

资料平台的项目图纸、图片、文字与厂家文档仍由各自作者或权利人持有；仅记录可追溯链接与短索引，不将其标为本项目原创。references/learned中的内容为本项目自行归纳的工作方法，保留来源与适用边界。

## 相关链接

[MIT说明](https://opensource.org/license/mit) · [GitHub开源许可说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository) · [ezdxf](https://github.com/mozman/ezdxf) · [Shapely](https://github.com/shapely/shapely) · [OR-Tools](https://github.com/google/or-tools) · [Scrapling](https://github.com/D4Vinci/Scrapling)
