# LibreCAD 无头 DWG 后端（可选）

日期：2026-11-15 · 状态：**blocked / 待真实往返验证** · 入口：`workbench_dwg_bridge`

## 这是什么

一个**可选、外部、离线**的 DWG / DXF 互换通道，用来补两个具体缺口：

| 缺口 | 以前 | 现在 |
| --- | --- | --- |
| 把生成的 DXF 交成 DWG | 必须 Windows + 已运行 AutoCAD + 有效许可 + MCP 会话授权 | 不需要 AutoCAD，调用外部 LibreCAD CLI |
| 读客户发来的 DWG | 需要 AutoCAD 或让用户自己转 | 外部 CLI 转 DXF 后进入现有 ezdxf 流程 |

它**不替代**活动 CAD 连接：不读活动文档、不写 AutoCAD、不做原生预览、不生成原生 DWG 对应验收。转换结果是交换文件，不是交付成果。

## 三条硬约束（先读完再用）

1. **许可证**：LibreCAD 是 GPL-2.0。本仓库**不打包二进制、不链接、不导入、不分发**，只以 `subprocess` 外部调用用户自己安装的命令行程序。仓库应用代码仍是 MIT。用户自行承担其安装与使用条款。
2. **DWGSUPPORT**：LibreCAD 官方 README 明确写着 `DWG input and output require a build with DWGSUPPORT enabled`。master 分支的 CMake 构建默认定义了该宏并有 `console_dxf2dwg.cpp`；旧稳定版、qmake 构建或第三方打包**不保证**带 DWG 支持。所以本模块不假设它存在，一律先探测。
3. **Windows GUI 陷阱**：Windows 上 `LibreCAD.exe` 是 GUI 子系统程序，交互命令行或 PowerShell 会在转换结束前返回，**且不设置退出码**。因此本模块**从不把进程返回码当成功依据**：`dxf2dwg` 读 DWG 文件头 `AC10xx` 签名，`dwg2dxf` 用 ezdxf 实际解析，并且都会等待产物落盘稳定。这条是设计核心，不要"优化"掉。

无显示环境建议设置 `QT_QPA_PLATFORM=offscreen`（模块已自动补默认值）。建议用 LibreCAD 官方 `continuous`（2.2.2 alpha / master）构建；`2.2.1-latest` 与第三方包以 `probe` 结果为准。

## 安装与探测

把可执行文件路径告诉运行时，或让它出现在 PATH 上：

- 环境变量 `LUOMU_CAD_LIBRECAD` 指向 `librecad` / `LibreCAD.exe` 的完整路径
- 或让 `librecad` 在 PATH 中可被 `shutil.which` 找到

模块**不猜测**任何安装目录，也不会替你安装或下载 LibreCAD。

```
workbench_dwg_bridge(operation="status")
```

返回 `found`、可执行文件来源、`commands_listed_in_help`。注意：Windows GUI 构建常常对 `-h` 不输出任何文本，此时命令列表记为 `unknown` 而不是"不支持"——空输出既不能证明支持，也不能证明不支持。

真正判定要跑一次最小往返：

```
workbench_dwg_bridge(operation="probe")
```

它在临时目录写一份最小 R12 DXF，执行 `dxf2dwg` → 验证 DWG 头 → 执行 `dwg2dxf` → 用 ezdxf 解析回来。只有全链通过，`round_trip_verified` 才为 `true`。这一步是**真实外部程序调用**，不是模拟；本机未装 LibreCAD 时会明确返回 `missing` / `unsupported`，不会虚报。

`probe` 通过后，才应把 `capabilities.yaml` 中 `offline-dwg-exchange` 从 `blocked` 提升为 `pilot`，并在 `evidence` 里记录本机实际版本与返回报告。

## 转换用法

```
workbench_dwg_bridge(operation="convert",
                     direction="dxf2dwg",
                     source="<已有的 DXF 绝对路径>",
                     target="client-a/plan.dwg",
                     version="r2000")
```

```
workbench_dwg_bridge(operation="convert",
                     direction="dwg2dxf",
                     source="<客户给的 DWG 绝对路径>",
                     target="client-a/received.dxf",
                     version="r2007")
```

- `direction`：`dxf2dwg` 或 `dwg2dxf`
- `source`：只读输入，允许安装目录之外的绝对路径，后缀必须与方向匹配，上限 200 MiB
- `target`：**相对名**，落在安装目录的 `outputs/dwg-bridge/` 之下；越界（含 `..`）直接拒绝
- `version`：DWG 输出可选 `r2000`（默认）/ `r2004` / `r2007` / `r2010` / `r2013` / `r2018`；DXF 输出可选 `r12` / `r14` / `r2000` / `r2004` / `r2007`（默认）/ `r2010` / `r2013` / `r2018`
- **拒绝覆盖**：目标已存在就返回 `output_exists`，换一个新名字。转换在临时目录完成，读回通过后才原子提交；未验证的产物不会留在输出目录里。

## 验证边界

| 做了 | 没做 |
| --- | --- |
| DWG 文件头签名 + 最小体积校验 | 几何逐实体比对、图层/线型/字体的语义保真 |
| DXF 用 ezdxf 实际解析 + modelspace 实体计数 | 转换前后数值一致性判定 |
| 输入 / 输出 SHA256、字节数、耗时、进程输出尾部 | 标准合规、图幅、打印样式、工程批准 |
| 最小 DXF → DWG → DXF 真实往返探测 | 各版本 DWG 的跨版本兼容性矩阵 |
| 明确的 `accepted_for_delivery=false` | 客户验收、盖章、交付签认 |

返回里始终带 `source_fidelity_verified=false`、`engineering_approval=false`、`accepted_for_delivery=false`、`delivery_review_required=true`。**转换成功不等于可以交付**；按项目约定仍要走 `workbench_delivery` 的独立审查。

## 故障排查

| 现象 | 原因与处理 |
| --- | --- |
| `missing` | 没找到可执行文件；设置 `LUOMU_CAD_LIBRECAD` 或加进 PATH |
| `unsupported`（help 有输出但缺命令） | 该构建不是 master 分支的命令行转换器，或未带 `DWGSUPPORT`；换 `continuous` 构建 |
| `probe` 的 `dxf2dwg_failed` | 构建不带 DWG 写入；`dxf2dwg` 不是所有发行版都有 |
| `not_verified` / `no stable output appeared before timeout` | Windows GUI 提前返回、转换仍在跑或失败；看返回里的 `stderr_tail`，必要时调大 `timeout` |
| `unsafe_output_path` | `target` 用了绝对路径或 `..`；改成相对名 |
| `output_exists` | 拒绝覆盖；换名字，不提供强制覆盖参数 |
| `wrong_output_suffix` | 目标后缀与方向不符 |
| `dwg-magic` 版本不符 | 构建忽略了 `-V`；去掉 `version` 用默认值 |

## 相关文件

- 实现：`src/luomu_cad/dwg_bridge.py`
- MCP 入口：`src/luomu_cad/server.py` 的 `workbench_dwg_bridge`
- 回归测试：`tests/test_dwg_bridge.py`（模拟外部程序，不依赖真实 LibreCAD）
- 能力登记：`capabilities.yaml` 的 `offline-dwg-exchange`
- 上游说明：https://github.com/LibreCAD/LibreCAD （Command-Line Converters 一节）
- 通用运行方式：`usage.md`、`cad-engine-usage.md`（同目录）
