# MCP使用与验收范围

日期：2026-11-05

摘要：离线绘图和实时CAD共享协议入口，拥有不同的操作条件和验收范围。

## 完整安装与首次验证

先按[README安装步骤](../README.md)将完整仓库安装到宿主指定的Skill目录。run.ps1入口面向64位Windows；技能目录需要可写，首次依赖准备需要相应网络访问。仅阅读SKILL.md不会安装依赖、注册MCP或连接AutoCAD。

首次安装运行`powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action verify`，一次完成环境准备、真实MCP检查、示例出图、保存几何/哈希与PNG检查。确认最终ok=true、退出码0及检查项PASS。报告在runtime/verification/installation.json；输出路径必须属于当前安装目录。这个流程无需AutoCAD，也不验证活动CAD已连接。

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

环境准备好后，也可将command设为当前技能目录下的`.venv/Scripts/python.exe`，args设为`["-u", "<技能绝对路径>/scripts/entry.py", "serve"]`；均使用绝对路径。采用这个Python入口时，在宿主的环境变量设置中显式指定LUOMU_CAD_ROOT为本技能根目录、LUOMU_CAD_LIVE_WRITES为0，避免继承其他实例的目录或写入设置。

通过PowerShell启动的模板默认关闭活动CAD写入。已有明确的应用启动或活动图纸修改/另存任务时，在该模板args末尾添加-LiveWrites并重建会话；仅传document_token不能替代服务端写入开关。

连接成功后先读取工具目录，调用cad_adapt_session及cad_tool_schema核对接口；模型身份缺失时保持unknown。workbench_status可检查当前服务。工具没有在宿主出现时，先核对服务路径、启动日志和MCP配置；不要凭工具名称假装已调用成功。

仅允许shell的Agent可用scripts/entry.py经真实stdio MCP执行离线任务，无需宿主提供MCP设置界面。CLI单次call默认只读；活动CAD连续读写使用持久MCP会话，仍遵守下面的服务端开关、文档身份和回读要求。

## 离线图纸

spec的walls指定id、axis、thickness和可选closed。openings指定id、wall、kind、offset、width；offset沿墙轴累计测量，不允许跨角或相互重叠。rooms以at定位闭合外墙内的空间。schedules选择doors、windows、rooms；缺失高度与窗台参数在表格中标为待核实，不补造工程值。

workbench_generate输出DXF、PNG、输入参数、QA与manifest。job_id与请求绑定；相同job不同参数拒绝，已提交job验证文件哈希后返回旧结果。出错中断的任务保持待核验，不擅自重放。

workbench_patch_opening需要job_id、source_job、expected_revision、opening_id和changes。改动组为该门窗、宿主墙与关联表格，其他实体哈希逐个核对。外部改过源文件、revision过期、目标不存在或尺寸非法时拒绝套用。

workbench_generate的墙体为中心轴直线多段线，先列出的墙拥有交接处，后列墙裁切至已存在墙边。圆弧墙及弧长洞口使用workbench_curved_walls；源清单复绘和固定比例PDF分别使用workbench_redraw与workbench_export_pdf，见[执行工具](execution-tools.md)。复杂错层、曲面节点和专业施工审查需要对应构造与计算。房间面积来自闭合外墙及实心隔墙区域，不将门洞相连空间合并为一间。

## 实时CAD

需要在同一Windows工作环境中已安装、且可通过ActiveX访问的AutoCAD。普通连接只附着已有实例；明确的启动任务通过服务端cad_start执行，不重启应用。离线出图成功不代表已经取得活动CAD实例；实机连接失败时应核对用户会话、进程权限和已运行版本，并按Skill约定保留断点重连。

以scripts/run.ps1 -Action serve提供MCP；只有已有任务授权才加-LiveWrites。客户端保持同一会话，cad_connect返回document_token，每个cad_mutate同时携带该token与operation_id。支持line、circle、arc、polyline、text、dimension、properties、save；save保存已有路径。新路径DWG另存调用cad_save_as，成功后使用返回的新token。显式启动调用cad_start；完整参数见[执行工具](execution-tools.md)。properties支持layer/text/height/color，没有任意命令或LISP入口。

活动文档身份改变、命令未结束或写入开关关闭时拒绝修改。cad_operation返回写入断点；started不代表成功，也不能直接用新ID重复执行。完成结果包含可回读的handle。能力边界由工具schema及实际读取结果确定，不宣称全版本支持。

CLI的call用于单次工具请求，默认只读；需要多个连续实时步骤时使用持久MCP会话。status --once是只读附着诊断，不是绘图验收。

## 验证范围与运行记录

2026-11-05补验0.3.1：官方uv下载/校验分支已实际执行；在PATH无uv/Python、无.venv且路径含空格/中文的新目录，以已校验uv安装包和Python/包缓存完成-Action verify。从其他工作目录使用生成的MCP配置实际完成工具列表与服务检查，默认写入关闭。完全无缓存的全部网络环境、宿主界面自动注册和其他电脑CAD实机操作仍未逐一验收。

2026-11-04已在公开仓库的独立下载副本，从无.venv、无runtime状态经run.ps1完成依赖准备、真实MCP自检和离线示例出图，并核对DXF/PNG等产物哈希。该次使用已有uv和Python/包缓存。无uv时的下载分支、各Agent宿主的自动发现/注册和其他电脑的AutoCAD实机读写未逐一验收。源码包独立环境62项软件测试通过，不等同所有宿主安装成功或工程验收。

维护者保留的自检、生成与软件测试证据位于私有runtime目录，未把私人日志、原始图纸或运行环境上传仓库。其他使用者运行后会在自己的安装目录产生.venv、runtime和outputs；这些目录应继续保持在版本控制之外。

## 相关链接

[示例参数](../examples/two-room.json) · [MCP协议](https://modelcontextprotocol.io/) · [AutoCAD AddLine](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-ActiveX-Reference/files/GUID-26C95029-14BB-40B9-9987-49EFC980CB9D.htm) · [AutoCAD AddDimAligned](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-ActiveX-Reference/files/GUID-9F5CE147-3787-4DD9-8028-8E89BF02A357.htm)
