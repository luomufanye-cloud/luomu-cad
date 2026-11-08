# 柜体共享尺寸与多视图出图

日期：2026-11-08

摘要：由同一毫米模型生成柜体平面、正立面和所选分格的侧向轮廓或板件剖面，回读原生尺寸、显示图元与跨图尺寸。本模块面向明确参数的柜体方案和参考尺寸图，不承担任意图片自动理解、五金加工或整套施工图。

## 入口与输入

```text
python scripts/build_casework.py build --spec examples/casework.json --output outputs/casework-01
python scripts/build_casework.py review --drawing outputs/casework-01/casework.dxf --manifest outputs/casework-01/casework-manifest.json
```

MCP `workbench_casework`：`operation=build` 传 `spec`、新 `output`；`operation=review` 传 `drawing` 和原 `manifest`。MCP路径限定在当前工作根目录，重复输出拒绝覆盖。活动 AutoCAD 的写入和验收继续通过 CAD MCP；离线输出不自动代表完成活动图任务。

- `width_mm`、`depth_mm`、`height_mm` 为真实毫米。`height_basis=body` 的柜身高不含顶部收口，总高加 `top_closure_mm`；`overall` 表示输入已含收口，柜身高需扣收口。踢脚属于柜身，不额外叠加。
- `front_widths_mm` 是正面模数尺寸链，合计必须等于柜宽，不是扣除板厚后的格内净宽。不得把六格各550当成六个内净空550。
- 有墙间净宽时，显式给 `opening_mm` 和 `install_gaps_mm=[左缝,右缝]`；净宽须等于柜宽加两侧安装缝。
- `interiors[].shelves_mm` 是层板下表面离地标高，`rod_mm` 是挂杆示意中心标高。无源尺寸时，不从画面分格间距臆造生产参数。
- `reference_outline` 不引入板厚，仅表达明确外形和内部示意；`panel_section` 必须提供 `panel_mm`、`back_mm`，生成顶、底、背板及选定格层板的边界。示例18/9是设计输入，非行业默认。侧剖不含门板厚度、铰链、安装孔、连接工艺和开料表。
- `section_bay` 从1计数，平面A-A位置及箭头对应所选格。平面X/Y、正立面X/Z、侧面Y/Z共用尺寸；独立标明视图，不暗示已有整栋建筑投影关系。

## 尺寸与纸面表达

输出为原生 `DIMENSION` 及显示块，不用文字覆盖。分别标注柜宽、柜深、柜身高、总高、收口、踢脚及正面分格。改高度应同步改变立面和侧面，平面外形不随高度改变。

`sheet.scale` 控制注释、线型和纸面排版，不缩小模型实体。`lineweights_mm` 需一起给 outline、hidden、cut、annotation，采用DXF可表示的纸面毫米值。隐藏线独立分层并按比例设置线型缩放；示例线重不冒充全专业标准。

通过现有 `workbench_export_pdf` 或 `pdf_export.render_pdf` 按真实纸张/窗口/比例出图。模型空间图框大小为纸张毫米乘比例；例如A3、1:30的窗口 `[0,0,12600,8910]`、纸张 `[420,297]`，图框已内部留边，可显式使用零外页边距。MCP导出入口的输入须在其输出根目录内。查看实际PDF渲染和纸面线重，不能美化重画后判通过。

## 原生回读与独立来源

检查实体完整性、所有生成线段坐标、实际线重/线型/缩放、文字内容和位置、尺寸定义点/测量值/因子/覆盖、显示文字和显示图元；另查四组跨图尺寸及正面尺寸链。模型、图纸和尺寸显示块绑定哈希。

源尺寸检查额外提供 `requirements`，结构为：

```json
{
  "source": {"sha256": "原始文件的64位SHA256", "locator": "原图页码及尺寸位置"},
  "dimensions_mm": {
    "front.width": 2400,
    "front.body_height": 2300,
    "front.overall_height": 2400,
    "plan.depth": 600,
    "section.depth": 600
  },
  "tolerance_mm": 0.001
}
```

CLI 加 `--requirements <独立尺寸.json> --source <原始文件>`；MCP同名参数接收对象及路径。来源哈希错误和尺寸缺项/不符均不能通过。源数值由独立读图或任务书确认，禁止从输出反填。哈希证明文件身份，不能证明转录或图像理解正确。

## 标准、来源和完成范围

中国室内项目继续走 `interior` 标准路由，核对地区、阶段及合同。出版社目录核实到 JGJ/T244-2011 的投影、立面、剖面、视图布置与图纸深度章节；目录不代替条文验收。机械尺寸标准只用于相应机械/产品任务选路。

研究对照了正投影教材、DXF尺寸接口及两个公开木工项目的尺寸、板厚、间隙和非法参数边界。应用代码由本项目独立编写，未复制这些项目的生成器、图库、五金或默认材料参数。来源与许可见[来源记录](casework-sources.json)。

测试覆盖两种高度口径、变高联动、分格/内部布置、错误输入、保存后几何/尺寸/显示图元/样式篡改、源文件变更、输出保护、CLI及真实stdio MCP。用户参考另以独立尺寸转录核对；尺寸子集通过不能报告整张源图线稿复刻通过。其他房间立面、天花、机电和整套图册需各自实现和验收。

## 相关链接

[示例模型](../examples/casework.json) · [实现](../src/luomu_cad/casework.py) · [专业检查](professional-cad.md) · [标准基础](standards-foundation.md)
