# 膜材管口与检验诊断训练

日期：2026-11-05

摘要：在管根完整主题中补充配件识图、搭接偏心、检验计时及漏水诊断。膜材与涂膜体系分别记录，不合并参数。

## 来源与应用

已阅读Schluter官网KERDI安装说明和水试验FAQ，实际查看11/2025配件表第2页。目录开口、管材公称规格、型号和膜厚分别识读，SI目录值不作为公英制精确换算或现场适配证明。安装资料区分拼缝、管口和变形缝的处理；模拟检验先排除堵头漏水，避免将试验装置问题直接归因于膜层。

## 练习与结果

运行python scripts/train_membrane_interfaces.py，结果写入runtime/training/membrane-interfaces。

- 四份DXF：目录SI尺寸圆环及自拟拼缝示意，另设单位错读、缺开口、搭接不足三种错误；回读保存的圆和多段线，查看正常题预览。
- 三组计算：125mm宽带覆盖零间隙对接缝，偏心0、10、15mm时分别核算两侧覆盖；最后一组最小侧47.5mm，另一侧足够也不能通过。本题采用52mm最小侧目标，不作为厂家公差。
- 七个模拟检验场景：正常、堵头漏水、过早开始、低温沿用原排程、未标水位、观察不足和水位下降原因不明，均形成对应诊断。
- 独立计时：自拟末道粘结11月5日08:00完成，室温下等待24小时，再观察24小时，结束点为11月7日08:00。养护与观察属于两个时间段。

原文、图页和哈希仅保存在本地研究记录；公开包不含原PDF或照片。目录几何与模拟诊断没有证明实体配件适配或现场水密，管根完整主题仍按专业清单继续。

## 相关链接

[配件目录](https://assets.schluter.com/asset/570120892212/document_5rkfn06c550dd9mg07usc03a3t/waterproofing.pdf?content-disposition=inline) · [安装说明](https://www.schluter.com/schluter-us/en_US/Membranes/Waterproofing-%28KERDI%29/Schluter-KERDI/p/KERDI) · [水试验FAQ](https://www.schluter.com/schluter-us/en_US/faq/shower-system-water-test-how-to) · [技术卡](technical/pipe-collar-seams-and-water-test.json)
