# WorkBuddy打包与验收

日期：2026-11-05

摘要：同一套Skill正文与源码生成通用源码包及WorkBuddy市场包。市场包补齐平台元数据，验收区分包结构、实际运行、GitHub下载与平台审核。

## 包格式

从源码仓库运行python scripts/build_workbuddy.py生成dist/luomu-cad-workbuddy-版本.zip。ZIP内只有一个luomu-cad根目录，最多保留一级子目录，文件路径最多三段。模块置于luomu_cad，资料分别置于references、technical和learned，运行脚本置于scripts，示例置于examples。发布工具和软件测试从源码仓库使用，不装入市场运行包。不要把通用source.zip或单个SKILL.md当作市场上传包。

WorkBuddy元数据来自references/workbuddy-market.json，version读取pyproject.toml。必填字段包含name、display_name、display_name_en、description、description_zh、description_en、version和author。构建器依据通用SKILL.md及源码生成市场包，转换目录相关的导入和资料链接，并检查资源可达性；正文工作流和业务逻辑保持一致。通用入口保留name/description，供其他宿主按标准发现。

## 运行前提

参考资料阅读不需要第三方Python依赖。离线DXF生成需要Python 3.11/3.12、依赖包和本机子进程权限；首次准备依赖需要可访问包源。依赖未就绪时预检输出具体缺项，不以安装成功或加载Skill代替任务成功。

Windows可使用scripts/run.ps1自动准备环境。其他可运行Python的环境可执行：

```sh
uv sync --python 3.11 --managed-python --locked --no-editable
.venv/bin/python scripts/preflight.py --mode offline
.venv/bin/python scripts/verify_install.py
.venv/bin/python scripts/verify_tasks.py
```

uv本身需要在该环境可用；未安装时按部署环境的允许方式准备，不下载未校验的可执行文件。不允许联网安装或子进程的环境只能读取资料，不能完成离线文件任务。

活动AutoCAD仅支持同一Windows桌面环境；云端Linux沙箱不能连接本机AutoCAD。预检、离线验收和发布测试均不连接或修改活动图纸。

## 发布检查

发布前审阅触发范围、步骤、示例、权限、适用条件及资源引用；检查私有信息和来源许可。运行全量软件测试、实际包安装及verify_tasks正常/错误任务。WorkBuddy包须从实际ZIP解压复测；GitHub更新还须下载指定提交的新副本并复测，保存提交号、ZIP哈希、命令退出码、结果和产物哈希。发布文档中的测试范围须与实际证据一致。

本地或GitHub副本的测试不等同WorkBuddy市场沙箱通过。市场审核结果以平台返回为准，未取得成功结果时不能标注已通过审核。

## 相关链接

[WorkBuddy官方Skill规范](https://open.workbuddy.cn/docs/skill) · [使用说明](usage.md) · [Skill入口](../SKILL.md)
