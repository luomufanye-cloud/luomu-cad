# MCP使用与验收范围

日期 2026-11-27

摘要：同一通用包提供标准 Skill 目录、stdio MCP 服务和命令行入口。活动 CAD 需要本机 Windows 会话。

## 按宿主能力接入

从[公开发布页](https://github.com/luomufanye-cloud/luomu-cad/releases/latest)下载通用源码包，解压为 `luomu-cad` 目录。按宿主允许的能力使用下列入口，可同时配置 Skill 和 MCP。

| 宿主具备的能力 | 接入方式 |
| --- | --- |
| 发现 Agent Skills | 将完整 `luomu-cad` 目录放到宿主支持的项目级或用户级技能目录。刷新后应能读取 `luomu-cad/SKILL.md` 和随附资源。[Agent Skills 规范](https://agentskills.io/specification) |
| 启动本地 stdio MCP 服务 | 自检后按宿主格式填写生成的 `command`、`args` 和 `env`。服务启动后调用 `workbench_status` 确认版本与输出目录。[MCP 传输规范](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports#stdio) |
| 运行终端命令和子进程 | 使用 `scripts/entry.py` 访问同一套离线工具。见[命令行示例](#命令行接入)。 |
| 读取本地或上传资料 | 读取 `SKILL.md` 和需要的 `references`。执行绘图须由具备上述工具条件的环境完成。 |

常见宿主的技能目录和刷新方式见各自文档。[Claude Code](https://code.claude.com/docs/en/skills) · [Cursor](https://cursor.com/docs/skills) · [VS Code 的 Copilot 与 Codex](https://code.visualstudio.com/docs/agent-customization/agent-skills) · [Gemini CLI](https://geminicli.com/docs/cli/skills/) · [OpenCode](https://opencode.ai/docs/skills)

Luomu CAD 的软件与解压安装已在 Windows 和 Ubuntu 验证。宿主的发现、工具注册和独立审查角色加载需要各自确认。云端如果只接收 HTTP MCP 地址，需另有可用的远程服务。本包的活动 AutoCAD 入口运行在同一台 Windows 电脑上。见[1.0 实测范围](release-validation-1.0.md)。

## 完整安装与首次验证

先按[README 安装步骤](../README.md#快速开始)解压完整通用包。使用 Agent Skills 时放入宿主指定的技能目录。使用 MCP 或命令行时，运行环境需要能访问并写入包目录，首次依赖准备需要访问相应包源。

Windows 使用 `scripts/run.ps1 -Action verify`。已装 uv 的 Linux 或 macOS 可运行 [Python 自检](../README.md#一条命令验收安装)。自检通过真实 MCP 生成示例并核对 DXF、文件哈希和 PNG。确认退出码为 0、最终 `ok=true` 且各项为 PASS。报告在 `runtime/verification/installation.json`，安装自检的范围是离线任务。

同一安装验证会自动把 `luomu-cad-reviewer` 原生子代理定义安装到当前仓库的项目作用域。要让另一个明确的客户项目使用它，运行同一入口并传 `-AgentProjectRoot '<客户项目根目录>'`，可通过 `-AgentHost codex/claude/t3/auto` 选择宿主；Python对应 `scripts/verify_install.py --reviewer-project-root <项目> --reviewer-host auto`。该过程不修改模型、Provider或权限，不覆盖已有用户代理。完整源码包带原生角色定义；仅复制一个Skill文件不能保证任意宿主立即发现子代理。宿主信任、新会话和实际独立执行必须按[安装说明](reviewer-installation.md)核实。

客户交付先按[分行业索引](industry-delivery-index.md)选本次图种与标准，交付前默认委派独立验收员并运行[客户交付检查](customer-delivery.md)。安装通过是运行环境验收，不是客户图纸通过。

仅需服务轻量自检时仍可用-Action health，检查ok=true、transport=stdio-mcp和当前目录下的output_root。相对Spec路径按技能根目录解析；从其他目录调用脚本时使用脚本绝对路径，外部工程Spec也用绝对路径。

## 接入Agent的MCP宿主

已经暴露随包MCP工具的宿主可以直接调用。安装验收成功会生成runtime/mcp-config.json，内含本机绝对路径和默认只读的服务条目，优先据此合并宿主配置，保留已有其他服务。其他支持MCP的宿主需按自己的格式填写服务并重新加载工具。下例适用于使用mcpServers字段的JSON配置；其他宿主按其配置格式填写同样的command和args，不能把JSON格式假定为所有宿主通用。

```json
{
  "mcpServers": {
    "luomu-cad": {
      "command": "powershell.exe",
      "args": [
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", "<技能绝对路径>/scripts/run.ps1",
        "-Action", "serve"
      ]
    }
  }
}
```

把<技能绝对路径>替换为该电脑的实际安装路径；路径作为单独参数传递，包含空格时也不要把整个命令拼成一个args元素。先在终端完成health，避免首次依赖安装超过宿主的MCP启动超时。

环境准备好后，可将 `command` 设为虚拟环境中 Python 的绝对路径。Windows 对应 `.venv/Scripts/python.exe`，Linux 和 macOS 对应 `.venv/bin/python`。将 `args` 设为 `["-u", "<技能绝对路径>/scripts/entry.py", "serve"]`，并显式配置 `LUOMU_CAD_ROOT` 为技能根目录和 `LUOMU_CAD_LIVE_WRITES=0`。

通过PowerShell启动的模板默认关闭活动CAD写入。已有明确的应用启动或活动图纸修改/另存任务时，在该模板args末尾添加-LiveWrites并重建会话；仅传document_token不能替代服务端写入开关。

连接成功后先读取工具目录，调用cad_adapt_session及cad_tool_schema核对接口；模型身份缺失时保持unknown。workbench_status可检查当前服务。工具没有在宿主出现时，先核对服务路径、启动日志和MCP配置；不要凭工具名称假装已调用成功。

## 命令行接入

安装自检通过后，在包目录运行下面的命令。命令行会启动随包 stdio MCP 来检查服务和生成离线示例。

```sh
uv run --no-sync python scripts/entry.py health
uv run --no-sync python scripts/entry.py generate examples/two-room.json --job demo-001
```

生成的 DXF、预览与 QA 随结果返回。活动 CAD 的连续读写使用持久 MCP 会话，按下文核对文档身份和写入授权。

## 离线图纸

spec的walls指定id、axis、thickness和可选closed。openings指定id、wall、kind、offset、width；offset沿墙轴累计测量，不允许跨角或相互重叠。rooms以at定位闭合外墙内的空间。schedules选择doors、windows、rooms；缺失高度与窗台参数在表格中标为待核实，不补造工程值。

workbench_generate输出DXF、PNG、输入参数、QA与manifest。job_id与请求绑定；相同job不同参数拒绝，已提交job验证文件哈希后返回旧结果。出错中断的任务保持待核验，不擅自重放。

workbench_patch_opening需要job_id、source_job、expected_revision、opening_id和changes。改动组为该门窗、宿主墙与关联表格，其他实体哈希逐个核对。外部改过源文件、revision过期、目标不存在或尺寸非法时拒绝套用。

默认在原图上修改：job_id只是本次修改的操作标识，结果先在临时暂存目录生成并核对范围外实体，通过后替换source_job目录内的plan.dxf、spec.json、qa.json和preview.png，暂存目录随即删除；核对失败时原图不变。返回的job_id仍为source_job，edit_job_id为本次job_id，下次修改使用返回的revision；原地修改后用原spec重放workbench_generate，返回的是这张图的最新状态。只有用户明确要求保留原图时才传new_copy=true，在job_id目录另建副本。

workbench_generate的墙体为中心轴直线多段线，先列出的墙拥有交接处，后列墙裁切至已存在墙边。圆弧墙及弧长洞口使用workbench_curved_walls；源清单复绘和固定比例PDF分别使用workbench_redraw与workbench_export_pdf，见[执行工具](execution-tools.md)。复杂错层、曲面节点和专业施工审查需要对应构造与计算。房间面积来自闭合外墙及实心隔墙区域，不将门洞相连空间合并为一间。

## 实时CAD

需要在同一Windows工作环境中已安装、且可通过ActiveX访问的AutoCAD。普通连接只附着已有实例；明确的启动任务通过服务端cad_start执行，不重启应用。离线出图成功不代表已经取得活动CAD实例；实机连接失败时应核对用户会话、进程权限和已运行版本，并按Skill约定保留断点重连。

以scripts/run.ps1 -Action serve提供MCP；只有已有任务授权才加-LiveWrites。客户端保持同一会话，cad_connect返回document_token，每个cad_mutate同时携带该token与operation_id。支持line、circle、arc、polyline、text、dimension、hatch、properties、save；save在已有路径原地保存，是修改后的默认落盘方式。新路径DWG另存调用cad_save_as并传explicit_request=true，仅在用户明确要求另存时使用，成功后使用返回的新token。显式启动调用cad_start；完整参数见[执行工具](execution-tools.md)。properties支持layer/text/height/color，没有任意命令或LISP入口。

活动文档身份改变、命令未结束或写入开关关闭时拒绝修改。cad_operation返回写入断点；started不代表成功，也不能直接用新ID重复执行。完成结果包含可回读的handle。能力边界由工具schema及实际读取结果确定，不宣称全版本支持。

CLI的call用于单次工具请求，默认只读；需要多个连续实时步骤时使用持久MCP会话。status --once是只读附着诊断，不是绘图验收。

## 验证范围与运行记录

2026-11-05补验0.3.1：官方uv下载/校验分支已实际执行；在PATH无uv/Python、无.venv且路径含空格/中文的新目录，以已校验uv安装包和Python/包缓存完成-Action verify。从其他工作目录使用生成的MCP配置实际完成工具列表与服务检查，默认写入关闭。完全无缓存的全部网络环境、宿主界面自动注册和其他电脑CAD实机操作仍未逐一验收。

2026-11-04已在公开仓库的独立下载副本，从无.venv、无runtime状态经run.ps1完成依赖准备、真实MCP自检和离线示例出图，并核对DXF/PNG等产物哈希。该次使用已有uv和Python/包缓存。无uv时的下载分支、各Agent宿主的自动发现/注册和其他电脑的AutoCAD实机读写未逐一验收。源码包独立环境62项软件测试通过，不等同所有宿主安装成功或工程验收。

维护者保留的自检、生成与软件测试证据位于私有runtime目录，未把私人日志、原始图纸或运行环境上传仓库。其他使用者运行后会在自己的安装目录产生.venv、runtime和outputs；这些目录应继续保持在版本控制之外。

## 相关链接

[示例参数](../examples/two-room.json) · [MCP协议](https://modelcontextprotocol.io/) · [AutoCAD AddLine](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-ActiveX-Reference/files/GUID-26C95029-14BB-40B9-9987-49EFC980CB9D.htm) · [AutoCAD AddDimAligned](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-ActiveX-Reference/files/GUID-9F5CE147-3787-4DD9-8028-8E89BF02A357.htm)
