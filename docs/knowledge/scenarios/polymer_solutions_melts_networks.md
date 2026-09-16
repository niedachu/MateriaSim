---
{
  "type": "knowledge",
  "doc_kind": "scenario",
  "doc_id": "materiasim.kb.scenarios.polymer_solutions_melts_networks",
  "title": "单链、溶液、熔体与交联网络",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "auhl-melt-equilibration",
    "polyply-2022",
    "grossfield-uncertainty"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.scientific_knowledge.materials_and_validation_bc"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
    "implementation": "not_implemented",
    "evidence": "not_assessed",
    "applicability": "not_assessed"
  },
  "limitations": [
    "仅核读来源登记所列章节；未完成特定模型主文、SI、数据及参数文件的联合复核",
    "本页为参考与本地审查规则，不是独立专家认证或可执行配置"
  ],
  "rag_exclude": false
}
---

# 单链、溶液、熔体与交联网络

## 共同起点与不同问题

先完成[聚合物身份](../models/polymer_identity_and_building.md)和[模型兼容](../models/force_field_compatibility.md)。以下是本地场景设计清单，不是一份通用 NVT→NPT 输入。

| 分支 | 除共同身份外需要的输入 | 准备和协议选择依据 | 观察量与停止条件 |
|---|---|---|---|
| 单链 | 真空、隐式或显式溶剂；链初态集合 | 真空链不能代表溶液链；显式溶剂需溶剂模型与盒子检查 | \(R_g\)、端到端与链内距离分布；不同初态持续不一致则不能报平衡平均 |
| 聚合物溶液 | 质量／数目口径、浓度、链分布、水／盐与电荷 | 从稀到浓不能只缩盒子；检查链间接触、溶剂化与有限尺寸 | 链统计、组分分布、目标量相关时间；出现未解释相分离或慢漂移则暂停结论 |
| 熔体／无定形固体 | 分布、目标密度／压力、温度与制备历史 | 消除近接与恢复链统计是不同任务；温度历程须有材料依据 | 多尺度内部距离、链间结构、密度与目标性质；密度稳而链仍变不算完成 |
| 预定义交联网络 | 交联图、未反应位点、环和悬挂链、制备参考态 | 先核对网络拓扑与残基反应后的参数；溶胀和力学协议另设计 | 连通性、缺陷、溶胀比及参考体积；图或参数缺失直接阻断 |
| 动态成键／断键 | 反应机制与适用势、速率／采样目标 | 不属于固定拓扑常规装配，必须另立模型与引擎评估 | 不能用“距离小于阈值加键”自动声称真实反应动力学 |

这些停止条件是审查触发项，不是已实现的自动判定器。没有给出通用阈值；阈值须在具体研究计划中预先说明。

## 为什么不能仅看密度平台

Auhl 等的长链珠簧模型研究使用沿链内部距离诊断结构，并讨论快速引入排斥造成的局部形变。其模型和制备方法有明确前提；该结果提示应检查不同链尺度，不能据此照搬真实聚合物的软势或准备时长。[作者预印本 §II、IV 及相关准备讨论](https://arxiv.org/pdf/cond-mat/0306026)

可设计的诊断包括：
\[
D(s)=\left\langle |\mathbf r_{i+s}-\mathbf r_i|^2\right\rangle_{i,\mathrm{chains},t}.
\]
位置须沿正确键连接重建，\(s\) 是链上间隔，\(D\) 单位 nm²。比较不同 \(s\) 的准备前后曲线，而不只看两端或一个 \(R_g\)。平均权重和支化链路径另行声明，不能把全体系原子顺序当主链顺序。

polyply 的建模／熔体示例说明坐标构建可以工具化，不提供对所有材料的平衡保证。[polyply](https://www.nature.com/articles/s41467-021-27627-4)

## 一次研究应提交什么

- 原始链集合、构建算法／工具版本、构建与速度种子、重排映射。
- 每个准备阶段的目的、约束释放与温压选择理由、失败情况。
- 预声明的生产窗口和可追加预算；若延长模拟，保留原分析与追加理由。
- 对同一目标量检查时间相关与独立初态差异；若未覆盖慢过程，报告条件性结果，不写“已收敛”。[不确定性最佳实践](https://livecomsjournal.org/index.php/livecoms/article/download/v1i1e5067/913/2595)

交联度、溶胀比和模量的精确定义取决于化学和实验测量；本轮不替代相应材料主文、SI 和实验条件审查。

## 项目状态

当前 [GROMACS 绑定](../../../src/materiasim/engines/gromacs/specification.py)不提供上述聚合物构建／网络流程。这些知识用于选择后续实现与验证路径；不是新场景已经注册。统计方法见[采样](../verification/sampling_uncertainty.md)，C0 清单见[模板](../templates/specialized.md)。
