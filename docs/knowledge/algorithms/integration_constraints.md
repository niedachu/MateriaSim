---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.integration_constraints",
  "title": "最小化、积分与约束",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "steep/md 当前路线与约束、步长的科学解释",
  "source_refs": [
    "gmx-md",
    "gmx-em",
    "gmx-constraints"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/mdp.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
    "implementation": "mapping_only",
    "evidence": "not_assessed",
    "applicability": "not_assessed"
  },
  "limitations": [
    "参考知识，经资料对照；非独立专家认证或材料适用性批准"
  ],
  "rag_exclude": false
}
---

# 最小化、积分与约束

## 三种不同目的

最小化寻找局部低势能构型，不生成目标温度下的平衡样本。GROMACS steepest descent 沿力方向尝试位移，并根据能量改变调整步长；达到步数上限与达到力收敛阈值须分别报告。[能量最小化](https://manual.gromacs.org/current/reference-manual/algorithms/energy-minimization.html)

无耦合、无约束的 leap-frog 核心更新为：

\[
\mathbf v_{n+1/2}=\mathbf v_{n-1/2}+\Delta t\,\mathbf F_n/m,\qquad
\mathbf r_{n+1}=\mathbf r_n+\Delta t\,\mathbf v_{n+1/2}.
\]

\(\Delta t\) 是时间，速度位于半步。不能把不同积分器的同一速度文件不加判断地当成相同初态；加入温压控制与约束后需用相应算法。[官方 Eq.29](https://manual.gromacs.org/current/reference-manual/algorithms/molecular-dynamics.html)

约束要求例如 \(|\mathbf r_i-\mathbf r_j|^2-b^2=0\)；它不同于有限弹簧常数的 restraint。LINCS/SHAKE 处理约束，SETTLE 面向刚性水。约束失败是需要定位的数值症状，不是唯一根因诊断。[约束算法](https://manual.gromacs.org/current/reference-manual/algorithms/constraint-algorithms.html)

## 选择与局限

| 配置 | 选择依据 | 修改后的检查 |
|---|---|---|
| 最小化力阈值与步数 | 初态、力场、后续协议 | 是否真达到目标；大力与重叠是否仍存在 |
| 时间步长 | 最高频自由度、约束和目标误差 | 收敛趋势、能量行为、目标统计量 |
| 约束对象与算法 | 模型定义和引擎支持 | 约束误差、自由度、警告及参数一致性 |
| 状态交接 | 初速度生成或检查点继承 | 种子、时间原点、continuation 与原始输入 |

不提供适用于所有材料的“安全 2 fs”。在适当 NVE 对照下的能量漂移检查只是数值证据，不能证明模型准确或慢过程已平衡。

## 本地映射

[MDP 适配](../../../src/materiasim/engines/gromacs/mdp.py)当前接受最小化 steep、动力学 md，并限制 dt ≤ 0.002 ps。这是项目边界，不是通用科学上限或推荐值。本轮不改该边界、协议或引擎算法。

后续验证设计应包括减小步长后的统计量／漂移对照及约束残差；必须先确认轨迹保存了所需产物并明确预算。本页没有新增这些数值试验。
