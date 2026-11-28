# 共享 CAD 任务、操作授权与审查状态

日期 2026-11-25

摘要：近期多项目共用 AutoCAD 的实际记录中，出现过其他任务仍在编辑、旧快照实体数已变化，以及先不保存后追加保存授权的情况。这里复用同一套协作占用和操作权限，避免每单重新实现；不连接 CAD、不认证用户身份，也不替代最终交付检查。

## 先区分本次任务的授权

编辑活动图、打开或切换文档、保存、关闭、导出分别记录为 `edit/open/save/close/export`。用户要求保留活动图且不保存、不导出时，不能因为有文件交付检查器就自动另存或打印；内部回读 JSON、检查预览与客户图纸导出分开。没有明确导出要求就不导出PDF、不打印；没有明确新文件要求就不新建、不另存，修改留在当前图纸上，`save` 权限只表示原路径保存。需要保存的后续指令到达后更新对应权限，未提到的原有权限保留。

通过 `workbench_cad_access` 查看真实 schema 后调用。例如：

```json
{"operation":"claim","task_id":"room-revision","permissions":{"edit":true},"authorization_source":"原始要求：只修改活动图，不保存、不导出、不关闭"}
```

claim 未提供的权限为 false；同一请求重复调用返回原占用。新增授权使用 `amend`、实际新指令出处和当前 `expected_revision`，只更新显式提供的权限。过期修订或悄悄扩大 claim 会报错。`release` 只释放协作占用，不保存、不关闭或激活图纸。

```json
{"operation":"amend","task_id":"room-revision","permissions":{"save":true},"authorization_source":"用户后续明确授权另存","expected_revision":1}
```

这些字段是对原始指令的记录，不能自行填 true 来获得用户没有授予的权限。既有服务端写开关、文档 token、当前命令与保存前提继续生效。

## 同一个 CAD 应用由谁操作

通用 MCP 会话先用 `list_documents` 读取当前实例，然后在打开、切换或批量修改前 claim，完成本轮独立检查及获授权文件动作后 release。其他参与会话仍可列文档和读取运行诊断，写入需等占用释放。没有 claim 的旧调用仍使用逐调用锁。来自同一 AutoCAD 进程的多个图纸标签共用同一个窗口锁。

参与服务使用 1.0.0 或兼容实现，并共享同一个协调目录。默认目录为技能根目录的 `runtime/cad-access`。跨安装时，在可信服务配置中设置相同的 `LUOMU_CAD_COORDINATION_ROOT`。连接后按实际应用 HWND 使用 `instances/<HWND>` 子目录。状态回执的 `instance_hwnd: null` 表示会话还未绑定 AutoCAD，显示的是启动前的占用状态。文件锁会在进程退出时释放，是否占用以锁为准。

这是参与服务器之间的协作机制，不锁定 AutoCAD 界面，不控制尚未接入的适配器。自定义任务 MCP 服务也须复用 `luomu_cad.cad_access.CadAccess`、相同协调目录和 `guard`；不能因为通用服务已更新，就声称旧任务服务器自动受保护。最终回读仍须核对用户是否切图、图纸是否变动。

## 不同 AutoCAD 实例并行

每个窗口注册一条独立的 stdio MCP 服务。一个 Agent 可以注册两个不同的服务名，多个 Agent 可以分别注册各自的服务。同机服务使用相同协调目录以及不同的实例配置名。Windows 启动参数示例，`-File` 使用各自安装中的绝对脚本路径。

```powershell
powershell.exe -NoProfile -File .\scripts\run.ps1 -Action serve -LiveWrites -InstanceProfile left
powershell.exe -NoProfile -File .\scripts\run.ps1 -Action serve -LiveWrites -InstanceProfile right
```

直接启动 Python MCP 的宿主可以用服务环境变量 `LUOMU_CAD_INSTANCE_PROFILE` 设置配置名。配置名以小写英文字母开头，最多 32 字符，可包含小写英文字母、数字和短横线。每条服务的工具调用保持使用同一个会话。

1. 用户明确授权启动实例后，在各自服务调用 `workbench_cad_access`，记录独立的任务 ID 和实际需要的操作授权。启动和新建图纸需要 `open` 授权。
2. 逐个调用两条服务的 `cad_start`，传该服务的 `operation_id`、`explicit_request=true`，并按本机已注册版本选择 `progid`。确认成功回执的 `instance_pid` 和 `instance_hwnd` 各不相同，且 `cad_started=true`。启动使用同一个短期锁，完成后可并行处理图纸。
3. 在各自服务获得任务图纸的 `document_token`，后续只在对应服务使用该 token。两条服务可各自执行并回读结果，任务完成后分别 release。

专用服务通过显式启动获取新的 AutoCAD 进程。普通会话仍可连接已经打开的 AutoCAD。关闭或重启专用 MCP 后，如需再启动独立实例，重新核对进程和图纸，使用新的操作 ID。两个任务各用自己的源文件和输出路径。AutoCAD 安装、许可证和当前 Windows 会话须能够启动两个进程。若启动回执提示 `CAD_INSTANCE_NOT_ISOLATED`，该服务未取得专用实例。

## 修改后使旧证据失效

`workbench_compare_states` 比较两份已经取得的状态记录，字段为 `document_id`、`entity_count`，以及可取得的 `snapshot_sha256/saved/dbmod`。传入的文档身份应取实际 MCP 文档 token 或准确的任务绑定身份，snapshot_sha256 应为实际原生快照内容摘要。

- 实体数从 2166 变成 2161、文档身份改变、快照指纹改变或已知保存状态改变，都返回 `stale`，重新读取受影响的原件与图面再审查。
- 相同实体数、相同 DBMOD 不能证明对象位置、文字或尺寸未变。没有两份强指纹时返回 `insufficient_evidence`。
- 两份强指纹匹配只返回 `matching_recorded_state`。该工具不连接 CAD，始终 `live_cad_verified=false`、`accepted_for_delivery=false`；不能把同一份旧记录重复传入后冒称实时核验。

最终审查必须绑定最新实际状态。任务只允许活动图时如实记录未保存；任务要求已保存交付时，继续执行原有原生文件与最终回读检查，不把未保存图转换为文件交付通过。

## 多页出图与设计类任务的经验

学校多页换框应先冻结本次源文件与模板哈希，只复用确认一致的模板，不复用上次项目的正文、身份和页数。检查目录重复项、原生尺寸、逐页倍率及用户新增的倍率约束；打印前后验证源对象、颜色和打印设置是否按本次范围保留。白底低对比 ACI 文字应在本次出图配置中处理，不能顺手改全图实体颜色；合并 PDF 后核对页数和每页实际纸张，不自动缩放内容。

纯设计与忠实复绘分开。用户明确允许设计时，可以列出设备包络、工况和布置等采用值并做计算校核，不能把此前“不可补设计”的复绘约束机械沿用；采用值仍不等于厂家参数或已经验证的运行能力。后续澄清写入本次任务有效依据，历史文字不要继续冒充当前状态。

相关链接：[任务与模型流程](model-workflow.md)、[原生 CAD 验收](native-validation.md)、[客户需求与交付检查](customer-delivery.md)、[PDF 表现](pdf-presentation.md)。
