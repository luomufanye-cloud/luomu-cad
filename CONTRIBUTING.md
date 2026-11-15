# 参与 Luomu CAD

感谢你愿意动手。这个项目的核心不是"能画更多图"，而是**"画出来的东西经得起追问"**。所以贡献规则和一般开源项目不太一样，先读完再改代码。

## 先读三份文件

| 文件 | 作用 |
| --- | --- |
| [capabilities.yaml](capabilities.yaml) | 能力等级、运行条件与验证证据的**唯一真源** |
| [SKILL.md](SKILL.md) | Agent 执行时必须遵守的工作流与边界 |
| [references/release-validation-0.16.md](references/release-validation-0.16.md) | 当前版本到底验证了什么、没验证什么 |

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

- 安装失败、出图不对、能力咨询 → 用对应的 [issue 模板](.github/ISSUE_TEMPLATE/)
- 想加新行业图种或新专业 → 先开 issue 说明**规范依据来源**，不要直接提交标准条文全文（第三方资料没有再分发权）
- 不确定某个改动是否符合项目边界 → 先开 issue 问，比写完被退回省事

## 许可

提交即表示你同意以 [MIT](LICENSE) 许可发布你的贡献。你引用的第三方资料、规范条文、图例的权利归属不变，本项目不因此获得再分发权。
