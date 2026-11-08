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

## 交付前的默认独立复核

主代理在交付前委派 `luomu-cad-reviewer`，使用独立上下文，提供客户原始要求、原图/原文件、实际交付物及经确认的标准依据；不给预期答案或生成者的通过结论。角色复核需求覆盖、专业标准隔离、实际几何/尺寸/空间关系、跨图索引及纸面输出，调用真实交付检查器。它不画图、不改客户原件、不替客户删项。缺项或失败返回具体修复清单，不能放行。

最小交接材料是客户任务书和原始哈希、稳定需求编号、专业/地区/阶段、原始参考文件、最终图纸及PDF、标准条文依据、交付契约。审核结果逐项记录发现与文件/页码/构件位置，绑定本轮任务书及产物哈希，并包含不同于生成者的会话/审核标识。会话标识是流程记录，不能替代实际检查，也不是不可伪造身份认证。详细验收字段以交付检查器的实际 schema 为准。

## 宿主的真实边界

Codex 当前官方文档要求独立TOML文件具有 `name`、`description`、`developer_instructions`。角色继承父会话权限、模型 Provider 和 MCP，文件里的提示不能构成只读沙箱；安装器也不通过角色文件改变这些设置。用兼容版本打开受信任项目，新安装的自定义角色应在新会话核实发现，不承诺当前桌面会话热加入。

Claude Code 官方支持 `.claude/agents/*.md`。本角色不指定模型或权限模式，并禁用 Edit/Write/NotebookEdit；保留检查器所需的 shell 和 MCP 不等于安全隔离，不能把行为限制宣称为系统强制只读。首次创建某作用域的 agents 目录时，已运行会话需要重新加载；已有目录的后续修改以宿主实际发现为准。

本机 T3/CAD Code 的启动器设置独立 CODEX_HOME，已检查其安装的服务代码通过 `codex app-server` 使用 Codex provider。该事实仅支持 Codex 原生配置路径选择，不证明 T3 UI 已执行独立委派。T3、WorkBuddy或其他宿主若没有真实的独立上下文委派能力，必须报告未具备独立代理执行条件，不能退回生成代理自审后冒称独立审核。

## 验证说明

`install` 和 `verify` 的 `runtime_discovery_verified=false` 是有意区分文件配置与宿主实际加载。源码测试在隔离项目实际生成原生文件、调用CLI并检查幂等升级、用户冲突、改动检测、缺失依赖和目录越界。另有可选的真实Codex发现测试：使用完全隔离的测试HOME，信任只作用于测试目录，再核对角色是否实际进入宿主模型可见的角色列表；CLI不存在则明确跳过。本机0.167.0已通过该发现测试。宿主原生发现、真实独立审核及客户交付验证需要各自的运行证据，不能通过把字段改成true来替代执行。测试没有修改真实用户的信任配置。

## 相关链接

- [Codex官方子代理文档](https://learn.chatgpt.com/docs/agent-configuration/subagents)
- [Codex旧文档入口，当前重定向至上述文档](https://developers.openai.com/codex/subagents)
- [Claude Code官方子代理文档](https://code.claude.com/docs/en/sub-agents)
- [安装实现](../src/luomu_cad/reviewer_install.py)
- [安装测试源码](https://github.com/luomufanye-cloud/luomu-cad/blob/main/tests/test_review_agent_install.py)
