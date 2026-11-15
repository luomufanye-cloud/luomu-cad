---
name: 出图不对 / Drawing problem
about: 生成的 DXF/PDF 与预期不符、复绘缺项、几何检查报错
title: "[drawing] "
labels: ["drawing"]
assignees: []
---

<!-- "工具返回成功"不等于图纸正确。请尽量给出可核对的证据，而不是截图说一句"不对"。 -->

## 你期望什么、实际得到什么

- 期望：
- 实际：

## 入口与输入

- 调用的工具（例如 `workbench_generate` / `workbench_redraw` / `workbench_components`）：
- 输入文件或 spec（可脱敏后贴关键片段）：

```json

```

## 检查输出

```text
# qa.json / manifest.json / source-check.json 中的失败项
# 或 verify_redraw.py 的输出
```

## 范围判断

- [ ] 这是**生成**问题（新建图纸就不对）
- [ ] 这是**复绘**问题（与参考图不一致）
- [ ] 这是**局部修改**问题（改了一处，别处被带动）
- [ ] 这是**显示**问题（几何正确，但字体/线宽/比例不对）

## 是否涉及活动 AutoCAD

- 纯离线任务 / 活动 CAD 任务
- 如果是活动 CAD：AutoCAD 版本、是否开启 `LUOMU_CAD_LIVE_WRITES`

## 脱敏确认

- [ ] 已删除个人路径、客户信息与账号令牌
- [ ] 私人图纸未作为默认附件；如需复现，已改用最小化合成示例
