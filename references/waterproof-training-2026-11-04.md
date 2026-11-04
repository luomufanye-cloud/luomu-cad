# 墙地交界防水：从资料到离线示意与错误题

日期：2026-11-04

摘要：本批收集后继续学习防水交界，将已研读的连续增强概念转为原生DXF示意和可复现的断点题；所有坐标为任意示意单位，不提供施工采用尺寸。

## 来源与本批研读

复核[厂家白皮书](https://www.iyuhong.com.cn/bocupload/2021/07/05/16254827144126q4cts.pdf)PDF第37页的转角附加层图文，将其中“交界增强与连续衔接”的概念用于本项目原创示意训练，没有复制原图几何或读取图片尺寸。

本轮还读到[节点增强宝产品页](https://www.iyuhong.com.cn/waterproof-coating-245)的单组分材料说明，与此前[G103资料](https://www.iyuhong.com.cn/bocupload/2023/04/27/16825585281236mi6x5.pdf)的双组分体系作对照。学习结论是先识别材料体系，不能把另一产品的配料条件移用到该节点材料。具体产品当前版本及适用工况仍需按项目核对。

## 实际绘制与回读

运行scripts/train_waterproof_continuity.py，分别生成连续、转角后断开、缺失上翻三份DXF与PNG。用原生LINE和ARC表达训练路径，再重新打开已保存文件计算实际端点的连接关系；没有用输入标签或文字“合格”推断结果。

正常题应连通，断点题和缺失上翻题应不连通。额外回归题在保存后改动实际线端点，检查器必须指出连续性已改变。正常与断点题的图面已经实际查看。

```powershell
.\.venv\Scripts\python.exe scripts/train_waterproof_continuity.py
```

产物保存在runtime/training/waterproof-continuity。脚本可重复运行；原理示意、读回结果和缺陷题均属于训练资料。

## 能力进度与未覆盖项

[该子主题](technical/wall-floor-waterproof-continuity.json)记录为exercise_checked。它只证明已能绘制并回读指定示意路径；材料层厚、粘结、相容性、收头、现场试验与工程规范未由此验证。管根、地漏、真实尺寸节点及完整施工做法继续保留在学习队列，不能由这道题提升为整专业或实际项目通过。

## 相关链接

[技术卡](technical/wall-floor-waterproof-continuity.json) · [训练脚本](../scripts/train_waterproof_continuity.py) · [能力矩阵](professional-learning.md)
