# 三维实体建模与量测验收

日期：2026-11-08

作者与维护者：[luomufanye-cloud](https://github.com/luomufanye-cloud)

摘要：机械、产品和参数化三维零件可使用独立实体运行时，完成源程序执行、STEP 回读、特征检查、四视图和原坐标实体差异检查。Luomu CAD 的 `workbench_solid` 通过 MCP 服务端调用固定版本的独立命令行工具；活动 AutoCAD 仍采用原有 MCP 路径。

0.11.0 的应用层实现为 src/luomu_cad/solid_engine.py，版本记录、脚本捕获、重试收据、特征匹配、差异报告和流程验收均由本项目维护；仅几何计算使用安装的 build123d/OpenCascade 等底层库。

## 准备

使用 Python 3.11 和 uv，在单独目录运行：

```text
python scripts/prepare_solid_runtime.py --runtime <独立运行时目录>
```

安装记录使用 `references/solid-runtime-lock.json` 的固定版本，并将解释器位置写入本技能根目录的 `runtime/solid-runtime.json`。部署另一个技能副本时，复制机器本地的这份注册记录，或显式传入 `runtime` 解释器路径。不要把本机路径提交到仓库。依赖通过包管理器安装；不复制其他 CAD 环境的 OCP 二进制。

安装器可重复执行。模型程序以正常 Python 权限运行，执行前检查本次脚本；参数化建模程序不是沙箱。运行目录使用本任务单独的空文件夹，调用 `workbench_solid(operation="initialize", project=...)`。此步骤不安装第三方 Agent 指令，避免覆盖本项目技能规则。

## 定义、构建与检查

1. 从当前要求或图纸确定毫米尺寸、坐标方向、孔径、数量及允许误差。先保存特征要求 JSON；体积和包围盒区间由独立要求或公式确定，不能从生成结果反填。
2. 编写 build123d 程序；通过 `show_object` 交出实体。按运行时规定使用同一种建模 API。示例见 `examples/solid-mounting-plate.py`、`examples/solid-plate-requirements.json` 和 `examples/solid-plate-contract.json`。
3. 调用 `workbench_solid(operation="run", project=..., source=..., label=..., idempotency_key=...)`。首次发送前保存 key。同一 key、同一源文件和选项会复用原结果；有意修改源文件后使用新 key。返回的 `outputs.step` 为实际产物，可能相对项目目录。
4. 调用 `workbench_solid(operation="review", project=..., source=<实际STEP路径>, spec=<独立特征JSON路径>, contract=...)`。检查实体有效性、原生特征、外形尺寸和体积区间，并生成 front/right/top/iso 四张 PNG。报告和四视图独立归档，不依赖下一次渲染保留旧图片。
5. 修改已有零件时传入 `reference=<修改前STEP>`，并按要求设置允许增加、去除的体积区间。按 STEP 保存的原坐标比较，不自动居中、旋转或缩放。`removed_volume_mm3` 对应原模型独占体积，`added_volume_mm3` 对应新模型独占体积；相等的净体积不能证明几何未改变。

例如，保持原模型形状与位置时可使用：

```json
{
  "removed_volume_mm3": [0, 0.001],
  "added_volume_mm3": [0, 0.001]
}
```

这只是显式给定容差的示例。实际容差必须来自本单要求；全局体积差不能定位所有局部错误。精确布尔比较超时、退化或仅有近似比较时，精确差异检查不能通过。应重查保存的两份 STEP，不重建模型掩盖问题。

## 结果如何判断

- `status="success"` 仅代表工具运行成功。特征要求还必须满足 `check_spec.passed=true`；Luomu CAD 会将失败要求、缺失尺寸、四视图不全或精确比较不可用记为失败。
- `checks_passed` 描述本次明确提供的数值与特征检查。圆柱特征检查支持直径、数量和方向，不代表孔的位置、通孔/盲孔性质、螺纹、公差带和装配适配全部满足要求。检查实际四视图与源图，必要时读取特征的坐标及轴向。
- 图像外观比较、真实图纸识读和工程审批各自需要证据。报告保留 `visual_review_passed=false`、`source_fidelity_verified=false`、`engineering_approval=false`，不会将几何内核成功作为这些结论。
- 四视图会检查是否为空白。原生渲染失败、出现不可靠 OpenGL 诊断或视图空白时，使用 build123d 的真实 STEP 网格化及 Matplotlib Agg 生成 CPU 预览；保留原诊断、渲染后端、请求的 0.05 mm 网格精度及三角形数。CPU 预览是网格近似，不能代替原生几何量测或精确隐藏面判断。必须实际查看各视图；Linux 的实际运行条件仍需在目标环境核对。

## 中断与重试

`run` 结果不明时，调用 `workbench_solid(operation="run_status", project=..., idempotency_key=<原key>)` 查询原执行；不会再次执行源程序。`execution_uncertain=true` 时保持原 key 和源文件，不自动创建第二个版本。`context` 可以读取项目状态。初始化要求空目录，已有项目直接查询或继续操作。

## 验证记录与相关链接

2026-11-08 的 Windows CPython 3.11 实测通过安装板和阶梯轴的原生建模、STEP 回读、四视图、错误孔径及等体积错位拦截、同 key 重试和源文件冲突；额外通过实际 stdio MCP 创建、建模与检查。0.11.0 的独立实现重跑相同功能契约，并在新的内核环境验证。安装板的前视、右视、顶视、轴测 CPU 预览均已实际查看。这里使用明确参数的建模测试，不作为工程图片识读准确率或实物制造验证。

Luomu CAD 通过自有应用层完成建模流程、测量组织、特征匹配、输入绑定和独立归档。底层库的许可与分发范围见[依赖声明](../THIRD_PARTY_NOTICES.md#optional-solid-model-runtime)。

本模块采用经实际验证的 Luomu MCP 服务端调用路径，在独立进程中运行实体工具，记录几何、特征、预览及重试状态。

已有 CadQuery、IFC 与服装入口见[内核运行](cad-engine-usage.md)。上述路径均不等于模型权重训练或二维工程图片识图能力已提高。
