# 独立交付验收子代理的安装与调用

日期：2026-11-08

摘要：仓库提供 `luomu-cad-reviewer` 专责角色和安装器，为明确的项目根目录生成 Codex、Claude Code 原生子代理文件。角色配置、文件安装、宿主发现和实际独立审核分开验证；这不是模型权重训练，也不保证任意 Agent 软件自动支持多代理。

## 同一次安装配备角色

从完整 Skill 目录执行：

```text
python scripts/install_review_agent.py --project-root <明确的客户项目根目录> --host auto
python scripts/install_review_agent.py --project-root <同一项目根目录> --host auto --verify
```

Python安装入口可直接调用 `luomu_cad.reviewer_install.install(bundle_root, project_root, host='auto')`。`auto` 安装两种项目级原生定义，不访问账户，不执行模型请求，不修改全局配置、模型、Provider、权限或 MCP 连接。仅安装所需宿主可用 `--host codex` 或 `--host claude`。`--host t3` 安装 Codex provider 所用的原生项目定义，不创建未得到验证的T3专用格式。

生成路径为 `.codex/agents/luomu-cad-reviewer.toml` 和 `.claude/agents/luomu-cad-reviewer.md`，来源是随仓库分发的[角色正文](../agents/luomu-cad-reviewer.md)。原生定义包含完整指令，资源路径以项目根为基准。安装器先核对所有同名文件，发生冲突时不覆盖用户角色，不部分安装另一宿主；相同文件幂等，旧版由安装收据确认的自有文件才可升级。修改过的角色会被验证器明确报告，不能静默还原。文件写入采用临时文件加原子替换，目标不得经链接逃出明确项目根。

仅把 Skill 放在某个 `skills/` 文件夹，不代表宿主已发现它内部的子代理。安装入口必须实际调用本安装器，或使用仓库根已经提供的对应原生目录。使用已下载完整仓库作为项目时，原生目录必须随源码包分发；已有宿主信任和新会话条件仍适用。`agents/openai.yaml` 是 Skill UI 元数据，不是原生子代理定义。

## 独立 Codex Home 中的个人作用域

需要同一个 CAD Code/Codex Home 下的多个现有或未来项目都具备该角色时，明确选择个人作用域：

```text
python scripts/install_review_agent.py --codex-home <明确的独立CODEX_HOME>
python scripts/install_review_agent.py --codex-home <同一个CODEX_HOME> --verify
```

API为 `install_codex_home(bundle_root, codex_home)` 和 `verify_codex_home(codex_home)`。目标必须是已存在且明确指定的Home，脚本不会猜测或修改用户真实全局目录；`--codex-home` 与 `--project-root` 互斥。个人角色写到 `CODEX_HOME/agents/luomu-cad-reviewer.toml`，不是 `CODEX_HOME/.codex/agents/`。安装收据单独保存在该Home的 `.luomu-cad/reviewer-personal-install.json`。同名冲突、用户编辑、原子写入和自有升级规则与项目作用域一致，不覆盖他人角色。

个人角色的Skill资源目录必须是完整绝对路径，不随项目工作目录变化；安装器同时检查该资源包仍可访问。它不修改Home中的 `config.toml`、鉴权、模型、Provider、权限、项目信任或启用代理设置。使用同一Home启动的兼容会话可发现个人角色，项目仍须满足宿主的信任及子代理能力要求；相同名称的项目角色也可能按宿主优先级覆盖个人角色，不能假定安装一次就无条件控制所有宿主。

实际离线发现测试在一个隔离Home安装个人角色，然后分别从两个不同项目运行原生Codex可见输入检查，两个项目均未创建 `.codex` 目录，均实际看到同一角色；测试不修改真实用户或D盘Home。文件可发现仍不证明模型已经执行验收；每次交付必须有实际独立执行及检查证据。

## 交付前的默认独立复核

主代理在交付前委派 `luomu-cad-reviewer`，使用独立上下文，提供客户原始要求、原图/原文件、实际交付物及经确认的标准依据；不给预期答案或生成者的通过结论。角色复核需求覆盖、专业标准隔离、实际几何/尺寸/空间关系、跨图索引及纸面输出，调用真实交付检查器。它不画图、不改客户原件、不替客户删项。缺项或失败返回具体修复清单，不能放行。

最小交接材料是客户任务书和原始哈希、稳定需求编号、专业/地区/阶段、原始参考文件、最终图纸及PDF、标准条文依据、交付契约。审核结果逐项记录发现与文件/页码/构件位置，绑定本轮任务书及产物哈希，并包含不同于生成者的会话/审核标识。会话标识是流程记录，不能替代实际检查，也不是不可伪造身份认证。详细验收字段以交付检查器的实际 schema 为准。

## 确定性启动隔离验收进程

宿主模型可能口头声称已经委派，却没有真实spawn事件、子线程或结果。此时必须拒绝独立验收，不以该口头声明放行。仓库另提供由程序确定启动的独立CLI验收路径，避免把是否执行检查完全交给父模型自觉决定：

```text
python scripts/run_review_agent.py --packet <原始材料packet.json> --output <新的验收记录目录> --codex-home <明确的现有CODEX_HOME> --project-root <明确工作项目> --timeout-seconds 240
```

API为 `luomu_cad.review_runner.run(packet_path, output, codex_home, project_root=None, timeout_seconds=240)`，供父MCP工具直接调用。它启动真实新 `codex exec --ephemeral -s read-only` 进程，用CLI实际支持的 `developer_instructions` 装载本仓库canonical角色正文，并使用已有Home的模型、Provider和鉴权；不猜造CLI的 `--agent` 参数，不切换后端。调用进程的线程关联ID不会传入新验收进程。该模式准确标记为 `isolated_cli_reviewer`，不是声称T3界面已经进行原生spawn。

packet格式包含 `schema_version=1`、`contract_id`、`customer_brief:{path,sha256}`、`artifacts:[{id,path,sha256,sheet_id}]`，可加 `raw_sources` 和 `standard_sources` 两组同格式原始依据文件。`sheet_id`省略时取原件文件名去扩展名；必须逐张逐格式对应原始任务书。所有原件须位于packet目录内，不能放入producer报告、通过结论或预期答案。客户原始JSON任务书须包含完整 `requirements`（逐项稳定id及客户description）、`required_sheets`（sheet_id及formats）与 `scope`，不能从输出倒推需求清单。执行器核对原件哈希，保留输入路径、模型运行记录及实际产物的派生预览；预览沿用原始属性，客户原件不改动。DXF/PDF可以离线直接读取；DWG必须有下述Main MCP绑定证据，STEP/IFC等仍须对应实际原生检查链，不能仅凭文件哈希声称已读图。

任务书含 `original_task:{path,sha256}` 时，该文件必须以相同实际路径和哈希列为 `raw_sources[0]`。专用MCP对 `source:0` 的真实read事件与访问记录通过后，独立报告才绑定 `original_task_sha256`；同哈希换路径、仅列名或未真实读取均不能生成可用报告。

原生DWG的packet仍保留真实 `artifacts[].path/sha256/sheet_id` 与DWG格式，并新增 `native_evidence:{dwg_artifact_id:{snapshot:{path,sha256},source_artifact_id:"source"}}`。snapshot为Main CAD MCP实际稳定 `delivery_snapshot` 的原始JSON，并附带其完整 `correspondence_preview` 记录。公开工厂校验hook `validate_native_evidence(packet,packet_base)` 不要求packet文件已存在，返回 `bindings` 及 `tracked:{Path:sha256}`；校验DWG格式头/实际字节哈希、原始facts摘要、干净稳定状态与load/save来源、同sheet原DXF、完整PNG绑定，并独立重做严格native/source比较。所有DWG、DXF、snapshot和PNG依赖也进入 `_prepare` 的原tracked返回值。

只读服务对 `artifact:<dwg-id>` 返回明确标为 `main_mcp_bound_native_facts` 的原生原值、实际定义/尺寸/cache与来源；`native-snapshot:<dwg-id>` 另读捕获文件哈希/来源摘要而不重复大facts，不向模型传递生成者comparison/pass结论。完整对应PNG只复制到本轮新输出目录后查看，明确标为source-correspondence而非native Export或native纸面plot。native调用临时使用50000 token工具输出预算，供完整事实可见；不改变模型、Provider、权限或验收阈值。该JSON不是live `NativeDeliveryContext` 或身份认证，独立报告必须标明 `native_live_revalidation_required=true`；最终放行仍须Main MCP当前原生复读，不能把DWG替换成DXF或删除客户要求的原格式。

离线runner先在明确项目工作目录调用真实CLI的 `mcp list --json`，读取有效分层配置中的服务名，不启动服务，也不记录连接地址或鉴权内容；随后在本次执行逐名临时禁用。配置查询失败即拒绝启动，不能只禁用Home层而漏掉项目层。它只为本次调用临时配置一个随机名称的专用只读证据MCP，不写真实Home或项目MCP配置。shell/unified_exec、任意路径view_image、图片生成及网页搜索在本次调用收窄；实际证据图片由只读MCP返回，同时用CLI支持的 `-i` 附入，不需要shell。执行器保留宿主权限环境和鉴权，不通过提高权限绕过拒绝。它禁止操作运行中的CAD；涉及DWG的实际重开与原生读取仍由已有CAD MCP验收链另外执行，不能靠离线runner虚构。

专用服务 `scripts/review_evidence_server.py` 仅暴露 `review_inventory()`、`review_read(file_id)`、`review_view(file_id,preview_index)`。客户端不能提供路径、命令或修改操作；文件ID集合从原始packet固定为客户任务书、实际产物、原始参考和标准依据，lock不能添加文件或替换身份。服务每次读取前后重验原件哈希，只读原始JSON/文字、DXF图元/顶点/图层、PDF页尺寸/文字和源图尺寸；图像工具返回原件或绑定源文件的真实预览及哈希，不返回生成器pass。服务只向本轮新证据目录写访问记录，预览也仅由执行器写到该目录，客户原件不改动。

原始事实按同一次已核验SHA256的字节快照解析。尺寸事实分开提供基础DimStyle、实际实体override、合并后的有效样式、原生定义测量、文字定义及匿名块实际缓存文字，不能只看到基础倍率就断定最终显示错误。PDF物理描边复用交付检查器的实际painted-path遍历，保留Form、CTM与ExtGState影响，忽略没有描边的闲置w值；另提供按实际嵌套对象路径定位的页面毫米坐标和原始曲线路径，便于独立核对比例和纸边距离。工具不给expected或通过结论。未绑定的DXF外部图片、underlay、xref或OLE依赖在渲染前明确拒绝，不能让渲染器自行读取packet外的文件。

packet可含非空 `producer_id` 作为原始生成流程标识，不能包含生成者的验收报告或预期结果。它是流程元数据，不是身份认证；独立审核会话ID由控制器从真实原生 `thread.started` 事件绑定，不要求模型臆造。缺失或矛盾信息仍须如实报告。新增元数据时另存packet，保留旧输入及其运行证据。

runner记录进程PID、真实thread.started会话ID、完整JSONL工具事件、stderr和schema约束的逐项最终结果。每份必要原件必须有成功completed MCP读取事件，每个必要图面必须有返回实际image字节的view事件；事件的服务名、工具名、参数、原件哈希、图片哈希及响应摘要必须匹配专用服务实际落盘的访问记录。echo、其他命令、任意MCP成功或模型口头自报均不足。CLI通过实际支持的 `-i` 直接附入派生图面与原始参考位图，绑定路径和哈希的启动清单随证据保存。最终结构化JSON须与真实模型agent_message事件一致且有turn.completed。缺检查事件、结果缺失、漏需求、原件或Home配置变更、超时，或任何其他MCP/命令/委派、未完成证据调用、证据工具失败及宿主政策拒绝均拒绝；超时只清理本执行器拥有的进程树。工具事件和本机访问记录是运行证据，不是不可伪造的身份认证。

全局读取过某文件还不等于该文件在每项相关客户要求中都得到观察。执行器仅从原始任务书的明确 `artifact_ids` 和原始checks的 `artifact_id` / `source_artifact_id` 派生 `requirement_artifact_ids`，交给独立模型作为无结论的关联元数据；多份产物而原任务关联不明确时拒绝猜测。每条需求的观察必须精确覆盖本条全部应检产物，跨格式对应必须同时包含目标纸面和原生源的具体观察；另一条需求中的源文件观察不能替代。缺关联观察时 `independent_review_ready=false`，不能先给ready再让最终验收偶然发现漏项，也不能由生成者补写一句“已检查”。

`independent_review_ready=true` 表示已产生绑定本轮原件的独立观察文件；`agent_verdict` 保留该模型真实判断，整体拒绝永远保留为下游阻断，即使模型把各单项写成accepted也不能改造成放行报告。runner的总体 `accepted_for_delivery` 始终保持false，父工具必须再将独立观察绑定原始交付契约并调用 `delivery.review` 的实际文件、标准、图面和需求检查，才能形成最终交付结论。这样不会把完成一个模型调用当成客户图纸合格。模型调用失败、CLI政策拒绝或网络超时均保留真实日志并拒绝，执行器不修改权限、凭证或后端来绕过限制。

## 宿主的真实边界

Codex 当前官方文档要求独立TOML文件具有 `name`、`description`、`developer_instructions`。角色继承父会话权限、模型 Provider 和 MCP，文件里的提示不能构成只读沙箱；安装器也不通过角色文件改变这些设置。用兼容版本打开受信任项目，新安装的自定义角色应在新会话核实发现，不承诺当前桌面会话热加入。

Claude Code 官方支持 `.claude/agents/*.md`。本角色不指定模型或权限模式，并禁用 Edit/Write/NotebookEdit；保留检查器所需的 shell 和 MCP 不等于安全隔离，不能把行为限制宣称为系统强制只读。首次创建某作用域的 agents 目录时，已运行会话需要重新加载；已有目录的后续修改以宿主实际发现为准。

本机 T3/CAD Code 的启动器设置独立 CODEX_HOME，已检查其安装的服务代码通过 `codex app-server` 使用 Codex provider。该事实仅支持 Codex 原生配置路径选择，不证明 T3 UI 已执行独立委派。T3、WorkBuddy或其他宿主若没有真实的独立上下文委派能力，必须报告未具备独立代理执行条件，不能退回生成代理自审后冒称独立审核。

## 验证说明

`install` 和 `verify` 的 `runtime_discovery_verified=false` 是有意区分文件配置与宿主实际加载。源码测试在隔离项目实际生成原生文件、调用CLI并检查幂等升级、用户冲突、改动检测、缺失依赖和目录越界。另有可选的真实Codex发现测试：使用完全隔离的测试HOME，信任只作用于测试目录，再核对角色是否实际进入宿主模型可见的角色列表；CLI不存在则明确跳过。本机0.167.0已通过该发现测试。宿主原生发现、真实独立审核及客户交付验证需要各自的运行证据，不能通过把字段改成true来替代执行。测试没有修改真实用户的信任配置。

2026-11-08 已用既有模型 `gpt-6.1-sol` 实际执行隔离CLI验收：固定参数的1000×600mm绘图练习，输入为原始任务书、实际DXF和A4 PDF。第一轮模型完成3份原件读取及2幅图面检查后，因有效尺寸覆盖和PDF实际描边事实缺失而拒绝；补充真实只读事实与原始流程标识后，新独立会话再次实际完成同样5项检查，接受该练习的两项原始要求。客户任务书、DXF、PDF、附图、模型和阈值保持，旧拒绝报告保留；更新的是证据工具及流程元数据，未把模型结论改为通过。运行记录包含真实PID、会话、MCP事件、服务访问记录、原件与图像哈希及结构化结果。此结果验证的是该范围内独立验收执行链，不能当作真实客户施工图、各行业工程验收或图片识别准确率提升的证据，最终交付仍须实际文件验收。

## 相关链接

- [Codex官方子代理文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex旧文档入口，当前重定向至上述文档](https://developers.openai.com/codex/subagents)
- [Claude Code官方子代理文档](https://code.claude.com/docs/en/sub-agents)
- [安装实现](../src/luomu_cad/reviewer_install.py)
- [安装测试源码](https://github.com/luomufanye-cloud/luomu-cad/blob/main/tests/test_review_agent_install.py)
- [只读证据服务](../src/luomu_cad/review_evidence_server.py)
- [Codex原生exec事件结构](https://github.com/openai/codex/blob/main/codex-rs/exec/src/exec_events.rs)
