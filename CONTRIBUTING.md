# 参与 Luomu CAD

日期 2026-11-27

摘要：贡献者应提交可复现的测试、原件保护证据和适用范围。1.0.0 的两类改动可作为提交范例。

感谢你愿意动手。这个项目的核心不是"能画更多图"，而是**"画出来的东西经得起追问"**。所以贡献规则和一般开源项目不太一样，先读完再改代码。

## 先读三份文件

| 文件 | 作用 |
| --- | --- |
| [capabilities.yaml](capabilities.yaml) | 能力等级、运行条件与验证证据的**唯一真源** |
| [SKILL.md](SKILL.md) | Agent 执行时必须遵守的工作流与边界 |
| [references/release-validation-1.0.md](references/release-validation-1.0.md) | 当前版本的实测记录和适用范围 |

## 能力清单优先

任何功能改动，先改 `capabilities.yaml`，再改实现，最后改文档。

```yaml
- id: your-capability
  title: "一句话说清能做什么"
  entries: [workbench_xxx]
  status: pilot            # 新能力一律从 pilot 开始
  requires: [offline]
  evidence: ["references/xxx.md", "tests/test_xxx.py"]
  limitations:
    - "必须写出做不到的部分"
```

四条硬规则：

1. **没有真实执行证据，不得标 `verified`。** 测试通过不等于验证完成；脚本跑通不等于工程验收。
2. **新能力默认 `pilot`。** 升级到 `verified` 需要真实执行记录 + 回归覆盖 + 证据指针。
3. **`limitations` 不能为空。** 写不出限制通常意味着你还没测到边界。
4. **`evidence` 只能指向仓库内可追溯的文件。** 维护者私有的 runtime 日志不能作为唯一证据。

文档里如果出现与 `capabilities.yaml` 冲突的表述，以清单为准，并提 issue 指出冲突。

## 环境准备

```powershell
uv sync --python 3.11 --extra dev --no-editable
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts\build_release.py
```

三条都必须通过再提 PR。`build_release.py` 不只是打包，它还会做私有数据扫描和 Markdown 本地链接检查。

## 提交前自查

- [ ] 新增/修改的能力已在 `capabilities.yaml` 登记，状态与证据相符
- [ ] 新增测试覆盖正常路径**和**至少一个失败/拒绝路径
- [ ] `pytest -q` 全量通过（不要只跑你改的那个文件）
- [ ] `build_release.py` 通过，没有把私有路径写进任何文件
- [ ] 文档里的边界声明与代码实际行为一致
- [ ] 修改 `agents/luomu-cad-reviewer.md` 后，用 `reviewer_install.definitions(仓库根目录, 仓库根目录)` 同步随包的 Codex、Claude Code 和 CodeBuddy 角色

## 1.0.0 的验证方法

- 多窗口改动要记录每条 MCP 会话的实例 PID、HWND、图纸 token 和任务归属。通过各自的写入句柄使用 `cad_native_entity_data` 比对原生坐标，并实际发送一次跨实例 token 请求检查拒绝结果。记录并发时间时注明采集点。见[发布验证](references/release-validation-1.0.md#活动-autocad)。
- 原地改图的变更要覆盖连续修订、同一操作重试、旧版本冲突和替换中途失败。对比原文件与关联清单的 SHA-256，并验证恢复后的读取和继续修改。涉及 PDF 或另存时，分别测试默认调用和明确请求。相关用例见[开口改图](https://github.com/luomufanye-cloud/luomu-cad/blob/v1.0.0/tests/test_drawing.py)与[图册修订](https://github.com/luomufanye-cloud/luomu-cad/blob/v1.0.0/tests/test_shared_project.py)。
- 新版本应在同一提交对齐 Python、包元数据、锁文件、能力清单和首页。按发布工作流验证源码包及 WorkBuddy 包的解压安装，再确认 GitHub 发布标签指向已合并提交。见[发布工作流](https://github.com/luomufanye-cloud/luomu-cad/actions/workflows/checks.yml)。

## 本版贡献

- Claude Code 完成 Windows 登录环境修复和原地修订、显式文件输出的初版实现。见[启动修复](https://github.com/luomufanye-cloud/luomu-cad/pull/11)与[文件行为变更](https://github.com/luomufanye-cloud/luomu-cad/pull/12)。
- Codex 实现独立 AutoCAD 实例协调，补齐原地修订的中断恢复和独立尺寸检查，完成原生回读及发布验收。见[1.0.0 集成](https://github.com/luomufanye-cloud/luomu-cad/pull/9)。

## 发布包边界

发布脚本会拒绝包含以下内容的提交：

- 形如 `ghp_…`、`sk-…` 的令牌，或私钥块
- 指向本机个人目录的绝对路径（含用户目录、工作目录、系统配置目录）
- `vendor/` 目录下的捆绑第三方源码

**请在提交前自己扫一遍。** 把私人图纸、客户信息、登录数据、`runtime/`、`outputs/`、`.venv/` 留在版本控制之外——它们已经在 `.gitignore` 里，不要强行 `git add -f`。

## 不接受的贡献

- 把未验证能力标成 `verified`，或删掉原有的限制声明来"让文档好看"
- 引入 GPL/AGPL 依赖并静态或动态链接进本项目（本项目是 MIT；外部命令行工具作为**用户自行安装的可选后端**另议，需先开 issue 讨论）
- 新增任意命令执行、任意 LISP、桌面截图或绕过授权的活动 CAD 写入入口
- 用"模型返回成功"替代实际文件回读与几何检查
- 只删测试来让 CI 变绿

## 讨论与提问

- 安装失败、出图不对、能力咨询 → 用对应的 [issue 模板](https://github.com/luomufanye-cloud/luomu-cad/issues/new/choose)
- 想加新行业图种或新专业 → 先开 issue 说明**规范依据来源**，不要直接提交标准条文全文（第三方资料没有再分发权）
- 不确定某个改动是否符合项目边界 → 先开 issue 问，比写完被退回省事

## 许可

提交即表示你同意以 [MIT](LICENSE) 许可发布你的贡献。你引用的第三方资料、规范条文、图例的权利归属不变，本项目不因此获得再分发权。
