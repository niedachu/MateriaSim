---
{
  "type": "knowledge",
  "doc_kind": "foundation",
  "doc_id": "materiasim.kb.foundations.classical_md",
  "title": "经典 MD、模型与系综",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "固定拓扑经典 MD 的基础；非反应性模型参考",
  "source_refs": [
    "gmx-md",
    "gmx-preparation"
  ],
  "related_code": [],
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

# 经典 MD、模型与系综

## 问题与假设

经典 MD 用所选势能模型描述粒子相互作用，通过数值积分生成轨迹。它求解的是模型，不直接求解真实材料全部电子／化学过程；固定拓扑路线不能把相邻原子自动变成化学键。

\[
m_i\ddot{\mathbf r}_i=\mathbf F_i,\qquad \mathbf F_i=-\nabla_i U.
\]

\(m_i\) 是质量，\(\mathbf r_i\) 是位置，\(U\) 是势能。公式必须使用一致单位；摩尔能量约定见[单位](units_composition.md)。引擎执行力计算和积分，项目不重新实现这些内核。[GROMACS 全局 MD 算法](https://manual.gromacs.org/current/reference-manual/algorithms/molecular-dynamics.html)

## 从研究问题选择模型

| 决策 | 必须说明 | 不能默认 |
|---|---|---|
| 原子／粗粒化分辨率 | 粒子代表什么，目标性质和尺度 | 不同分辨率的时间和观察量可直接混用 |
| 系综 | NVE 的粒子数、体积、能量；NVT 的温度；NPT 的压力控制目标 | 写了 NPT 就证明得到正确分布 |
| 化学状态 | 连接、质子化、端基、表面修饰和净电荷 | 坐标文件就已包含完整模型 |
| 目标量 | 结构、平衡统计还是动力学量 | 任一稳定轨迹均能回答任一问题 |

这是本项目的研究选择规则，不是通用参数推荐。先确定问题和观察量，再选模型、工具和需要保存的产物。[官方体系准备](https://manual.gromacs.org/current/user-guide/system-preparation.html)

## 实现、验证和限制

当前核心只接入受限原子模型及 GROMACS 路线，见[能力矩阵](../platform/capabilities.md)。读懂 CG 或反应性 MD 不代表平台支持它们。

每项研究先列模型假设与可能失效原因，再把验证拆成[工程、数值、采样和适用性](../verification/evidence_levels.md)。本页为参考知识，不含新材料验证，也不为任何力场背书。
