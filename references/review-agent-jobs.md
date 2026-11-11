# 独立审查后台作业接口

日期：2026-11-11

摘要：固定 Python worker 调用真正的 `review_runner.run`，将长时间模型审查与短 MCP 会话分开。启动、轮询和断线重连不重复调用模型；证据就绪与客户交付验收严格分开。

## 可信服务器 API

```python
from luomu_cad import review_jobs

# base 必须来自服务器固定 ROOT，不能暴露为任意工具参数或从 packet 读取。
receipt = review_jobs.packet_from_contract(
    contract_path, packet_path, base=ROOT,
    source_base=ROOT, native_evidence=None,
)
state = review_jobs.start(
    operation_id, packet_path, output, codex_home,
    project_root=None, timeout_seconds=600, base=ROOT,
)
state = review_jobs.status(operation_id, base=ROOT)
```

`codex_home` 必须是调用者已经明确指定的现有目录，或可信服务器进程显式设置的 `CODEX_HOME`。没有该输入就报错；不可猜其他账号目录、模型、provider 或认证路径。该接口不修改认证、权限、trust 或全局配置。`project_root` 默认使用 packet 的所在目录，显式指定时也必须位于固定 ROOT 内。

main MCP 的 `workbench_review_agent` 提供 prepare/start/status 三种操作，直接传递结构化参数，不构造 shell，不允许 packet 指定 worker、executor、command、环境变量或 base。start 要求 `use_personal_codex_home=true` 显式授权使用所选账号已经配置的模型，status 只需要已有 operation_id，不启动模型。`scripts/review_job_worker.py` 必须随安装包携带；它同时支持 `ROOT/src/luomu_cad` 源码布局和 `ROOT/luomu_cad` 扁平安装布局。缺少固定 worker 时 fail closed。

prepare 的 `contract_base` 表示**合同内部原件路径的解析基准**，与最终 `workbench_delivery.base` 含义相同，默认固定 ROOT；它必须在 ROOT 内，并非扩大授权根目录。薄包装将其传给 Python factory 的 `source_base` 参数。直接调用 Python factory 时，未给 source_base 则保留合同所在目录的旧默认行为。packet 仍须位于能够包含全部原件的 ROOT 内目录，源路径只重基记录，不复制或重写原件。

## CodeBuddy / HY4 宿主参数

Python `review_jobs.start(..., codex_home=None, host="codebuddy", codebuddy_home=<现有Home>, model=<当前主会话模型ID>)` 直接调用 CodeBuddy。MCP start 同时要求 `use_personal_codebuddy_home=true`，不使用 Codex 账户选项。可信服务器可提供 CODEBUDDY_CONFIG_DIR 与 LUOMU_REVIEW_CODEBUDDY_CLI；不从 packet 读取执行命令、Provider 或凭证。

请求哈希同时绑定 host、codebuddy_home、model，同 ID 改模型报 JOB_CONFLICT。Codex 旧请求字段和默认行为保留。CodeBuddy 事件转换后复用相同的原件、图像、访问记录及最终交付门禁，超时或失败保留原始记录，不自动切换到 Codex。安装与调用见[子代理安装说明](reviewer-installation.md)。

Codex 路径也接受当前主会话 `model`，仅传递给本次 CLI 的模型参数，不改 CODEX_HOME 配置。未提供时兼容原来的 Home 配置行为。这样主聊天临时切换模型后，后台审查不必使用 Home 中旧的默认模型。角色安装和调度均不设 HY4 或其他模型家族白名单，实际可用模型由宿主和所选账号决定。

## 持久状态与重复请求

状态位于 `ROOT/runtime/review-jobs/<operation_id>.json`。ID 使用 storage.Journal 的 ASCII 字母、数字、连字符和下划线规则。请求哈希绑定：packet 路径、packet 及全部已声明原件的实际 SHA256、输出目录、显式 Codex home、项目目录、模型执行时限。

同 ID、同请求返回已有状态；同 ID、不同请求报 `JOB_CONFLICT`。已排队、已运行、启动失败和启动结果不明均不会自动再次启动。短会话丢失返回值后，继续用同一个 ID 查询。新模型重试必须由上层明确安排新的 operation_id 和新输出目录；不得因等待超时无条件换 ID。

输出目录必须是新目录或空目录，位于 ROOT 内，并与原件、Codex home、作业状态目录隔离。所有历史作业保留输出占用记录，拒绝相同或互为祖先的输出路径。runner 的输出保持独占。输入、输出和项目路径每次重新 resolve，阻止已变化的符号链接逃出授权范围。作业使用进程锁保护状态和输出预约；不删除已有文件、不取消 CAD 命令、不重启 CAD。

Windows worker 使用 detached/process-group 与隐藏窗口启动；POSIX 使用独立 session。stdin 为 DEVNULL，日志为对应作业的 worker.log。worker 不依赖父进程 Python 对象，但 **detached 不保证跨宿主强制清理存活**：真实 MCP SDK stdio 会话退出或 Windows 宿主清理可能终止整棵子进程树。实际使用应保持拥有该任务的 MCP 会话连接至审查完成，同时可从另一个 MCP 会话查询 status；T3 常驻 MCP 适用。短工具调用返回与销毁整个 MCP 服务会话不同，不能将前者测试推广成后者保证。

启动及 worker 认领时记录 PID 和进程创建标识（Windows GetProcessTimes FILETIME；Linux /proc starttime）。queued/running 的 worker 经只读系统查询已退出，或同 PID 的创建标识已变，status 将持久记录 failed 与 orphaned_worker，不自动重启、不重用输出、不声称 ready。老记录缺创建标识时，PID 确实不存在仍可判退出；仅有一个同 PID 活进程不能证明它是原 worker，也不能证明审查成功。权限拒绝或身份不可查询保持 unknown，不能猜死或猜活。宿主清理只是可能原因，错误记录不会伪称已经查明具体终止者。查询过程中若 worker 已提交终态，保留其真实终态，不覆盖成功报告。现有中断 journal、日志和输出不清空。

不使用 breakaway、提权或绕过宿主生命周期管理。超时清理沿用 runner 对自己 Codex 进程树的限定处理，不新增全局杀进程操作。相关系统语义：[进程标识与句柄](https://learn.microsoft.com/en-us/windows/win32/procthread/process-handles-and-identifiers)、[GetProcessTimes](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-getprocesstimes)。

## 返回 schema 与完成条件

公共状态至少包含：

```json
{
  "schema_version": 1,
  "operation_id": "review-001",
  "request_hash": "SHA256",
  "status": "queued",
  "accepted_for_delivery": false,
  "independent_review_ready": false,
  "execution_mode": "isolated_cli_reviewer",
  "model_weights_trained": false,
  "next_step": "..."
}
```

状态含义：

| 状态 | 含义 | 是否可当作交付通过 |
|---|---|---|
| queued | 已记录唯一启动意图，后台进程待认领；异常中断也保留此状态 | 否 |
| running | 固定 worker 已认领，尚未完成；PID 仅用于诊断 | 否 |
| launch_failed | 启动抛错，保留错误，不自动重放 | 否 |
| failed | runner 或输入/输出核查失败，或 worker 已证实退出/PID 已复用却无完成回执；可能含完整失败报告 | 否 |
| ready | 本次真实 runner 返回的独立审查证据经绑定检查后可用 | 否 |
| invalidated | 状态、请求、原件、报告、审查证据或绑定已变化 | 否 |

ready 额外提供 `result:{path,sha256}`、`independent_review:{path,sha256}`、`agent_verdict`。`agent_verdict=false` 也可能 ready：这表示独立审查完成并发现问题，仍需处理问题。`accepted_for_delivery` 在所有后台 API 中始终是 false。

worker 必须实际调用固定 runner，校验返回值与其落盘 `runner-result.json` 相同，核对真实 session、模型消息事件、证据读取、packet hash、输入清单与 independent-review 的任务/原件绑定；随后写入含 request_hash 和本次 nonce 的独占 receipt。status 仅接受该 receipt 引用且哈希一致的报告，复验全部 run 工件和原件哈希。仅有 PID、同目录随意放置的 runner-result 或制作方 passed 声明不能变成 ready。receipt/nonce 是本机执行关联，**不是密码学身份认证或抵抗本机任意写权限者的安全沙箱**。

最终必须将这份 independent-review 与**原合同**交给 `delivery.review`，重新打开实际交付文件并执行需求、格式、尺寸、标准等验收。后台 ready 不替代专业审核或法定审签。

## 从原合同生成只含原件的 packet

`packet_from_contract` 验证原合同与原 customer_brief 的 scope、jurisdiction、行业、稳定需求 ID、描述、原始 checks、图页及逐格式期望一致。对实际原件逐一核对文件哈希、行业、图种、图页和格式，保证完整格式清单与需求-artifact 关联不跨专业。

导出的内容为：

- contract_id、producer_id，二者只是身份元数据；helper 返回独立的原合同路径与哈希供控制器保存，不把整个含旧报告的合同交给模型。
- 原 customer_brief 文件的路径和哈希，**不改写其任何内容，包括 expected、checks 和 required_sheets**。
- 原交付物 id/path/sha256/sheet_id。行业、图种、格式在导出前按原 brief 严格验证，随后由原 brief.required_sheets 与 artifact.sheet_id、实际文件扩展名关联，不重复携带制作方元数据。移除制作方 artifact.expected、passed、旧 independent_review 和制作方结论。
- 原任务文件、原 brief 的 raw_sources，以及标准分配中的原 source_evidence；不导出标准审查结论 evidence 文件。标准所属行业须在该行业 allowlist 中。

packet 在原合同同目录或其 ROOT 内祖先目录创建，以便所有原件位于 packet 授权目录内。只独占新建 packet，不复制或转换客户文件，不重写任务书，不改动旧 packet。

直接支持实际 DXF/PDF。DWG 仅在 runner 与证据服务具有绑定原生证据读取器、且实际校验通过时开放：传入 `native_evidence={dwg_id:{"snapshot":{"path":"原始快照.json","sha256":"..."},"source_artifact_id":"source"}}`。factory 在新建 packet 前调用实际 `validate_native_evidence(packet, packet_base)` 校验，快照内部字段保持原样；没有新版读取器或证据不全则明确拒绝。原 DWG 始终保留在 artifacts，required_sheets 原格式不删改，不能拿 DXF 代替 DWG。快照和完整预览属于已绑定的历史观测，最终交付仍须由主 MCP 获取当前活动文档状态核验。IFC/STEP 等其他格式仍需其各自的原生读取路径，不以字段名支持代替实际读取。

## 验证范围

`tests/test_review_jobs.py` 使用受控的真实 Python 后台进程，以及既有 runner 的受控 Codex 事件 fixture；不请求模型 API、不碰 CAD、不证明识图准确率。覆盖短 start 返回后继续执行、跨新 API 进程读取状态、幂等/冲突、输出保护、篡改作废、超时、模型结果缺失/不匹配、证据读取拒绝、原合同行业隔离与扁平安装布局。真实模型执行能力由 runner 独立实测记录，不与这些 fixture 测试混淆。

相关文件：实现模块 `luomu_cad.review_jobs`（源码位于 `src/luomu_cad/review_jobs.py`）、[固定 worker](../scripts/review_job_worker.py)、源码测试 `tests/test_review_jobs.py`、[隔离审查入口](../scripts/run_review_agent.py)、[安装与角色说明](reviewer-installation.md)。源码模块和测试路径采用代码标记，兼容不携带 tests/src 目录的扁平安装包。
