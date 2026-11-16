---
name: 安装失败 / Installation failure
about: run.ps1、uv、依赖准备或 MCP 注册出问题
title: "[install] "
labels: ["installation"]
assignees: []
---

<!-- 先跑过 -Action verify 再提 issue。自检失败会返回非零退出码，只看到依赖装完不代表 Skill 可用。 -->

## 你执行了什么

```powershell
# 粘贴完整命令，例如：
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -Action verify
```

## 最终错误

```text
# 粘贴最后的错误输出，不要只贴"失败了"
# 如果生成了 runtime/verification/installation.json，请贴出其中的 checks 段
```

## 环境

| 项 | 值 |
| --- | --- |
| 操作系统与版本 | 例如 Windows 11 23H2 |
| Python 版本 | `python -V` 的输出 |
| uv 版本 | `uv --version`，没有就写"无" |
| Agent 宿主与版本 | 例如 CodeBuddy / Codex / Claude Code |
| 安装方式 | 完整仓库 ZIP / git clone / npx |
| 技能目录是否含空格或中文 | 是 / 否 |

## 退出码与 ok 字段

- 进程退出码：
- 最终 JSON 的 `ok`：
- `artifact_hashes` / `dxf_readback` / `preview_file` 各项结果：

## 脱敏确认

- [ ] 已删除个人路径、客户信息与账号令牌
- [ ] 没有附上私人 DWG/DXF 图纸
