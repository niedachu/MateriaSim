# ZIL 数量与重复编排工程验收

问题：同一核心能否按声明执行两个条件、四个有明确种子的 Run，并完整保留成功/失败与分析来源？

[research.json](research.json) 是唯一研究定义；[count_2](experiments/count_2.json) 与 [count_4](experiments/count_4.json) 分别使用 2/4 个 ZIL，每条件两次重复。固定 4.5 nm 周期盒、两个装填区域、现有 ZIL/TIP3P 参数包和短程协议；实际种子、预算、预期与失败判据均在定义中。

实验从根 examples 的 packed_zil_water 派生，不修改原资产。初始区域只用于装填，不限制后续动力学。填水数可能不同，不能将这个设计称为固定浓度对照。

用法见[研究指南](../../docs/guides/research.md)。生成结果必须放在源码外；普通运行不修改本目录。观察量为 prod 阶段 0.5 nm 下的逐帧唯一 ZIL 分子对数量，工程验收不输出平衡、结合自由能或材料性质结论。
