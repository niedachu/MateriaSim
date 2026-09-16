---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.solvent_ion_models",
  "title": "溶剂、离子与混合配方模型",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "joung-cheatham-2008",
    "gmx-genion",
    "gmx-topology"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py",
    "src/materiasim/engines/gromacs/parameters.py"
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

# 溶剂、离子与混合配方模型

## 把配方数量与相互作用选择分开

每次研究可改变组成，但水模型、离子参数、电荷方法、组合规则不是为了跑稳而随意调的旋钮。Joung–Cheatham 的单价离子工作针对指定水模型优化；本轮核查摘要，足以支持“匹配有条件”，不足以批准任意离子、浓度或混合溶剂的具体参数表。[原论文摘要](https://pubmed.ncbi.nlm.nih.gov/18593145/)

本地模型审查表至少包含：

| 模型 | 必填信息 | 关键拒绝条件 |
|---|---|---|
| 水 | 完整模型与实现版本、位点／虚拟位点、约束、配套非键设置 | 只写 TIP3P 而不核对具体实现与资产 |
| 有机溶剂 | 化学身份、电荷方案、纯相验证条件、与其他组分交叉项 | 纯液体密度对上就宣称混合物热力学可信 |
| 离子 | 价态、参数版本、匹配水／溶剂、优化目标和浓度范围 | 同一种元素的参数在各水模型间任意互换 |
| 混合物 | 各自作用和交叉作用、组成定义、参考实验／基准 | 两种已验证纯溶剂自动构成已验证混合物 |
| 特殊条件 | 高浓度、非水、极化／电荷缩放等假设及依据 | 从常规单价水溶液未经复审外推 |

## 盐、反离子和离子强度

先用整数粒子数解组成与电荷账本，再报告实际浓度。对指定体积 \(V\)（L）：
\[
c_i=\frac{N_i}{N_A V},\qquad
Q/e=\sum_i N_i z_i+Q_{\mathrm{other}}/e,\qquad
I=\frac12\sum_i c_i z_i^2.
\]
其中离子 \(N_i\) 必须包含既有离子、中和反离子和添加的盐；\(Q_{\mathrm{other}}\) 是未计入离子集合的其他组分电荷。离子强度这里按小离子组分的浓度定义；复杂带电聚合物不能直接被当作理想小离子外推实验活度。\(I\) 不等于盐配方浓度，离子强度也不等于活度。

GROMACS genion 通过替换溶剂添加单原子离子，浓度选项不扣除已存在离子，额外中和需要单独理解。操作后应重新核算离子数、溶剂数、电荷和体积口径。[genion 官方说明](https://manual.gromacs.org/current/onlinehelp/gmx-genion.html)

非 1:1 盐要使用化学计量整数，不把每种离子都设成相同数量。NPT 下用初始盒体积推算的目标值不能当作最终精确浓度；应声明使用参考体积、平均体积还是瞬时浓度平均。

## 混合物验证怎样分层

本地建议依次选择：纯组分身份与基本结构 → 配对作用和溶剂化 → 混合组成下密度／分布及目标性质 → 研究条件下的采样与实验对照。每层选哪些性质由研究问题决定，不强制一次计算全部性质。密度、活度、扩散等不能互相替代；未审具体方法时只登记为待选基准。

## 项目边界

当前绑定不接受显式 SOL 模型，受限 GAFF packing 要求显式组成中性；已有配套水资产不是任意混合溶剂／盐模块。[绑定代码](../../../src/materiasim/engines/gromacs/specification.py)、[导入边界](../../../src/materiasim/engines/gromacs/parameters.py)

本页不更换资产；[场景配方步骤](../scenarios/multicomponent_solutions.md)和[组成单位](../foundations/units_composition.md)负责记录任务选择，参数审查归[力场兼容](force_field_compatibility.md)。
