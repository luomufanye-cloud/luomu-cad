# 排布求解前核对真实边界与能力范围

日期：2026-11-04T10:04:24+08:00

摘要：经审阅的绘图工作方法，附来源与适用边界；不是工程参数或规范认证。

触发条件：家具、展陈或商业空间排布。先整理场地边界、固定障碍、出入口及保留通道、可移动对象、旋转条件和净距来源，再匹配求解器能力。不规则房间不能只取外包矩形就宣称布局有效；尚未实现的多边形边界、任意旋转或预留区域字段必须明确拒绝，不能忽略约束后返回成功。仅在项目分区范围已确认时将问题化为内含矩形子区，并说明结论只覆盖该区。已确认的矩形通道可显式列为不可占用障碍，结果逐项检查边界、相交和保留区。

## 适用边界

ampm的斜边平面、编号功能区以及RITCS的复杂场地平面用于启发约束分类。没有从案例反推尺寸或净距。当前工具仍只求解轴对齐矩形，不支持任意形状；本条改进是拒绝未支持约束，不是新增多边形求解能力。

## 相关链接

- [Erasmus Hogeschool RITCS by ATAMA, Brussels](https://www.gooood.cn/en/erasmus-hogeschool-ritcs.htm)；采集时间 2026-11-04T05:52:07+08:00
- [ampm Outdoor Lifestyle Collective by Inside Outside Studio](https://www.gooood.cn/en/ampm-outdoor-lifestyle-collective-by-inside-outside-studio.htm)；采集时间 2026-11-04T05:52:04+08:00
