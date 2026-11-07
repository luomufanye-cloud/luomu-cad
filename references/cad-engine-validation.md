# 上游 CAD 能力实测

日期 2026-11-07

摘要 记录本轮原装依赖、几何回读、结构评测和纸样输出的执行范围。真实源图的模型端到端准确率须另做固定测试集对照。

## 验证协议

- 结构评测包含完全匹配、错分类、遗漏、重复、关系错误、坐标偏移、源图不一致、自交及非法坐标。
- CadQuery 实测长方体、带孔圆环和放样，导出 STEP 后通过原装导入器核查实体、体积及包围盒。保存三方向 SVG 与可编辑程序。
- IfcOpenShell 实测 IFC4 墙、门洞、填充门，重新打开后检查关联及实际净体积。墙原体积 3 m³，门洞减除 0.378 m³，目标净体积 2.622 m³。
- FreeSewing 实测 Benjamin 领结，输入不同颈围，输出含曲线与缝份的 SVG，检查上游草拟错误与警告。其他设计包与工业格式尚需分别验证。

## 方法迁移范围

这些结果证明所列接口及检查实际运行。源图识读依赖当前视觉模型与输入质量。当前没有完成更换 Skill 前后的盲测对照，跨专业识图增益保持待验证。服装实穿、机械制造公差、工程系统计算和签署等按专业任务单独验收。

## 本轮执行结果

| 环境与入口 | 实际结果 |
| --- | --- |
| Windows / Python 3.11 主运行环境，启用 OCR、局部图像与 FreeSewing 实测 | 402 passed，5 skipped；跳过项为独立内核环境的测试 |
| CadQuery 2.8.0 + IfcOpenShell 0.9.0.post1 独立环境 | 6 passed，覆盖上述5项及共用的尺寸区间反例 |
| FreeSewing 4.10.2，Node.js 24 | 3组颈围与1项非法输入测试通过；从 npm 锁文件全新安装17个包后复测通过 |
| CadQuery 正常 CLI 入口 | STEP 回读为1个实体，80×50×8 mm，带孔净体积31095.221315766114 mm³ |
| IfcOpenShell 正常 CLI 入口 | IFC4 模式检查通过，1条洞口关系、1条填充关系，墙净体积2.622 m³ |
| 结构评测正常 CLI 入口 | 读取原图哈希、独立标注与预测，输出类别计数及几何匹配报告 |

内核运行环境与主 MCP/OCR 环境独立安装。Python 锁定记录包含53个已安装发行包版本，npm 锁文件含包完整性校验。首次直接安装 FreeSewing 时发现上游遗漏的 `@freesewing/config` 与 `@freesewing/plugin-transform` 依赖，已作为显式固定版本依赖纳入安装入口并重新验证。

源代码与 D 盘运行包通过对应文件哈希校验。CAD Code 技能重载后仍使用 gpt-6.1-sol/high。此次未提交新的宿主模型测试对话。

测试代码见 [结构评测回归](https://github.com/luomufanye-cloud/luomu-cad/blob/main/tests/test_scene_benchmark.py) 与 [实际内核回归](https://github.com/luomufanye-cloud/luomu-cad/blob/main/tests/test_cad_engines.py)。

## 相关链接

- [技术来源及拆解](cad-method-distillation.md)
- [安装与使用](cad-engine-usage.md)
- [既有专业验证](professional-validation.md)
