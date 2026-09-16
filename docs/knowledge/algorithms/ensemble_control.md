---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.ensemble_control",
  "title": "温压控制与场景协议",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "温压控制选型参考；非通用协议或生产批准",
  "source_refs": [
    "gmx-md",
    "gmx-preparation"
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

# 温压控制与场景协议

## 均值稳定不是系综正确

平衡系综要求的不只是温度／压力均值，还有相应分布与涨落。GROMACS 官方不建议新模拟使用 Berendsen 温压耦合；其压力耦合不能给出正确 NPT 涨落。V-rescale 与随机胞缩放等方案各有自己的算法与支持条件，不能把名称当作任意系统的自动批准。[温压耦合章节](https://manual.gromacs.org/current/reference-manual/algorithms/molecular-dynamics.html)

## 配置语义

| 类别 | 需记录 | 避免的错误 |
|---|---|---|
| 温度控制 | 目标温度、耦合组、方法和时间尺度 | 为了曲线平滑把耦合任意加强 |
| 压力控制 | 目标压力、可压缩性、耦合方向／时间尺度 | 对固相／界面无条件照搬水盒各向同性参数 |
| 自由度 | 约束、固定对象、质心处理 | 忽略不同处理对温度定义的影响 |
| 观察量 | 平衡结构或动力学性质 | 只核对静态分布就宣称动力学无偏 |
| 阶段 | 初态、继承量、松弛目的和退出标准 | 任意场景强制串同一套 NVT→NPT |

GROMACS 将 NVT、NPT 或其他目标系综视为按问题选择的阶段；某些步骤可选，不是全体系通用流程。[体系准备](https://manual.gromacs.org/current/user-guide/system-preparation.html)

## 如何在项目里使用

本页不自动改协议资产。先在研究设计中说明目标和选型依据，再核对[现有适配白名单](../../../src/materiasim/engines/gromacs/mdp.py)。有 MDP 键可解析，不代表所有键值组合已经过本项目验证。

均匀溶液、膜、刚性颗粒和可形变固体需要不同判断；没有具体材料与模型时，不推荐一套数值参数覆盖它们。采用候选协议后，检查温度／体积行为、相关分布及目标慢变量，证据按[分层要求](../verification/evidence_levels.md)保存。本页没有新增系综检验。
