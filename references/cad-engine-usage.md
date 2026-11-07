# 上游 CAD 内核运行

日期 2026-11-07

摘要 可选内核使用独立环境，常规 OCR 与 MCP 环境保持各自依赖。只有当前文件生成任务需要相应内核时才安装。本地参数化模型脚本经审阅后执行，具有普通 Python 进程权限。

## 准备环境

安装需要 Python 3.11、uv，服装入口还需 Node.js 24 与 npm。指定单独的运行时目录。

```text
python scripts/prepare_cad_engines.py --runtime <运行时目录>
```

脚本安装锁定的 Python 包及 FreeSewing npm 依赖。模型文件及参考资料保存在任务目录。生成脚本的外部访问、写入及依赖在执行前审阅。来源图片不通过此安装脚本上传。

## CadQuery

模型脚本导入 `cadquery`，使用明确的毫米参数，最终 `result` 为 Workplane、Solid 或 Compound。可使用原装内核的草图、曲线、布尔、旋转、扫掠、放样等 API。执行命令中的 Python 使用独立环境的解释器。

```text
<运行时Python> scripts/run_cad_engine.py cadquery examples/cadquery-part.py --output <任务目录>/part-01
```

输出包含可编辑 `model.py`、交换几何 `model.step`、三张正投影视图 SVG 和 `report.json`。STEP 自身的几何交换能力与源 Python 程序的参数化编辑能力分别保留。重复相同请求会验证文件哈希并返回已有记录，已改动输出要求使用新目录。

提供 `--contract measurements.json` 可校验独立源尺寸。区间由源尺寸、公差或已说明的测量误差确定。

```json
{"solid_count": [1,1], "bbox_mm": [[79.99,80.01],[49.99,50.01],[7.99,8.01]]}
```

`geometry_passed` 描述导出回读与给定区间。原图逐视图比较及孔槽、倒角、材料、制造公差仍需专业证据。`source_fidelity_verified` 和 `engineering_approval` 默认 false。

## IfcOpenShell

使用上游 API 创建 IFC 文件对象并赋给 `result`。接口的 SI 米参数与项目存储单位需明确换算。

```text
<运行时Python> scripts/run_cad_engine.py ifcopenshell examples/ifc-openings.py --output <任务目录>/building-01
```

输出 IFC、源程序与实际回读报告，包含模式检查、构件净体积、洞口宿主及填充关系。示例包含一面墙及门洞，验证重点为实际扣洞与关联。模型完整性、跨软件展示、房间空间关系与专业设计仍按项目检查。

## FreeSewing

显式传入已安装上游模块入口、导出类、量体设置和输出 SVG。

```text
node scripts/draft_freesewing.mjs <运行时目录>/sewing/node_modules/@freesewing/benjamin/src/index.mjs Benjamin examples/freesewing-settings.json <任务目录>/benjamin.svg
```

读取 SVG 和同名 `.svg.json` 报告，记录草拟错误、警告及哈希。量体采用毫米，缝份 `sa` 同样为毫米。其他设计包按上游要求准备完整测量字段。通用入口可调用其他已安装设计，当前实测范围见 [验证记录](cad-engine-validation.md)。

## 相关链接

- [方法拆解](cad-method-distillation.md)
- [CadQuery 文档](https://cadquery.readthedocs.io/en/latest/)
- [IfcOpenShell 文档](https://docs.ifcopenshell.org/)
- [FreeSewing 源码](https://github.com/freesewing/freesewing)
