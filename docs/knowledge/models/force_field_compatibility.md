---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.force_field_compatibility",
  "title": "力场与多组分模型兼容",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "非反应性原子模型的兼容审查；不提供未经验证的新参数",
  "source_refs": [
    "gmx-topology",
    "gmx-nonbonded",
    "joung-cheatham-2008",
    "lammps-hybrid"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/parameters.py",
    "src/materiasim/specs/purpose.py"
  ],
  "related_assets": [
    "catalog/interaction_bundles/packed_mixture_bundle.json",
    "catalog/models/cat_model.json"
  ],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans",
    "materiasim.plan.scientific_knowledge.materials_and_validation_bc"
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

# 力场与多组分模型兼容

## 为什么不能简单拼接

坐标描述初态；拓扑和参数描述相互作用。两个组分分别能编译，不说明交叉作用可靠。把一套模型的电荷、水模型或非键规则换掉，已改变物理模型，而不只是调整运行速度。

以 LJ 12–6 为例：

\[
U_{ij}(r)=4\epsilon_{ij}\left[(\sigma_{ij}/r)^{12}-(\sigma_{ij}/r)^6\right].
\]

\(\sigma\) 为长度，\(\epsilon\) 为能量。GROMACS 组合规则 2 使用 \(\sigma_{ij}=(\sigma_i+\sigma_j)/2\)、\(\epsilon_{ij}=\sqrt{\epsilon_i\epsilon_j}\)；不能未经审查应用到所有力场。[非键参数公式](https://manual.gromacs.org/current/reference-manual/functions/nonbonded-interactions.html)

## 兼容审查表

| 层次 | 核查内容 |
|---|---|
| 身份 | 键级、立体、端基、质子化、净电荷、分辨率 |
| 函数与单位 | 键合／非键形式、参数顺序、角度与力常数单位 |
| 全局约定 | defaults、组合规则、1–4 缩放、排除和显式 pairs |
| 跨组分 | 水／离子匹配、显式交叉参数、表面－溶剂与表面－溶质作用 |
| 资产完整性 | 原子顺序、类型、include 闭包、版本和来源 |
| 适用性 | 参数化对象、条件、目标性质、基准和失败范围 |

gen-pairs、fudgeLJ、fudgeQQ、nrexcl 等影响最终作用，不是可以忽略的文件装饰。[拓扑格式与 defaults](https://manual.gromacs.org/current/reference-manual/topologies/topology-file-formats.html)

## 资产映射与验收要求

实际组合资产见 [packed mixture bundle](../../../catalog/interaction_bundles/packed_mixture_bundle.json)，它声明 engineering_only；CAT 模型见[模型卡](../../../catalog/models/cat_model.json)。文件名里的 GAFF2/AM1-BCC 是来源线索，不代替参数化过程和材料适用性审查。

平台核对见[参数检查](../../../src/materiasim/engines/gromacs/parameters.py)与[用途政策](../../../src/materiasim/specs/purpose.py)。程序检查完整性不是完整的化学兼容专家系统。

接入新组合应先核对类型与作用项，在已定义协议下做数值对照，再依据目标性质选择物理基准。端基或表面修饰变化要重新判断模型身份和适用范围。本页没有批准任何新组合；未经验证的参数不加入正式推荐资产。

## B 批补充：相互作用审查不是文件清单

把所有组分列成上三角审查表：对角线是自作用，非对角线是交叉作用。每格填写模型版本、函数、参数来源或有依据的组合规则、适用条件和证据定位；空格不能被解释为“默认可靠”。

水／离子应作为相容组合审查，不能仅按元素名称选参数。[单价离子原文摘要](https://pubmed.ncbi.nlm.nih.gov/18593145/)
逐对表不足以审查多体势；不同子势的交叉项也不能假定自动混合。[LAMMPS 官方限制](https://docs.lammps.org/pair_hybrid.html)

本地审查分成三道关：**可表达**（引擎／导入器能完整表示）→ **实现一致**（转换后的单位、函数和数值匹配）→ **适用可信**（条件与目标性质有依据）。前一关通过不能代替后一关。缺失交叉参数、未经核查的电荷缩放或势函数变化，应登记缺口，不能通过放宽工程校验消除。

材料专属信息分别见[聚合物](polymer_identity_and_building.md)、[生物大分子](biomolecular_preparation.md)、[水／盐](solvent_ion_models.md)、[固体表面](solid_surface_nanoparticle_models.md)和[粗粒化](coarse_graining_and_transferability.md)。可填写审查表见[模板](../templates/specialized.md)。
