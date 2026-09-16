---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.polymer_identity_and_building",
  "title": "聚合物身份、连接与初态构建",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "polyply-2022",
    "mbuild-docs",
    "foyer-docs"
  ],
  "related_code": [
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

# 聚合物身份、连接与初态构建

## 先定义模型，不按材料简称自动选参数

以下是本地审查清单。一个可复现模型至少要确定：

| 身份层 | 应记录 | 缺失时如何处理 |
|---|---|---|
| 化学图 | 单体原子与连接位点、键级、立构、序列、端基 | 不从“PEG”“丙烯酸聚合物”等简称猜测 |
| 链拓扑 | 线性、环状、支化、接枝；支点与交联位置 | 不用坐标距离自动认定共价连接 |
| 链集合 | 每条链的聚合度、序列、数量和生成种子 | 平均链长不能代替实际链清单 |
| 化学状态 | 质子化、电荷、反离子；固定状态或其他模型 | pH 标签不能替代电荷与状态定义 |
| 参数身份 | 力场版本、分辨率、残基块、连接项、端基项及来源 | 有单体参数不等于有聚合后的连接参数 |

为明确分布口径，对链类别 \(i\) 的数量 \(n_i\) 与摩尔质量 \(M_i\)，本页使用
\[
M_n=\frac{\sum_i n_i M_i}{\sum_i n_i},\quad
M_w=\frac{\sum_i n_i M_i^2}{\sum_i n_i M_i},\quad
Đ_M=\frac{M_w}{M_n}.
\]
这是数量／质量加权平均的数学约定，\(M\) 用 g/mol，\(Đ_M\) 无量纲；不能混用聚合度分布与摩尔质量分布。端基和共聚序列不同，不能统一用“链长乘同一个单体质量”替代逐链化学组成核算。

## 四个分离的交付件

1. **化学图**：原子与连接的身份、明确的链端和支点。
2. **参数图**：各原子及跨连接的键、角、二面角、排除和特殊非键项。
3. **起始坐标**：对应参数图的原子映射、盒子、构象生成方式与种子。
4. **准备及采样证据**：采用场景协议后的结构与目标量检查。

polyply 将残基块、连接规则用于拓扑生成，再独立生成坐标；其构建时使用的简化表示不能自动解释为生产用 CG 力场。[polyply 主文 Parameter file generation / System building](https://www.nature.com/articles/s41467-021-27627-4)

mBuild 可以作为组件式结构构建候选；Foyer 的化学环境规则与优先级用于原子类型赋值。二者都不免除材料身份和参数覆盖审查。[mBuild](https://mbuild.mosdef.org/en/stable/)、[Foyer](https://foyer.mosdef.org/en/stable/)

## 本地接入检查与负例

- 核对序列、端基、连接后的净电荷、原子数；保存旧／新原子编号映射。
- 核对跨单体连接产生的所有参数项；无匹配或多义匹配应中止并给出定位，不静默取默认。
- 结构检查包括错误成键、异常近接、穿盒后的链连通性；通过这些仍不说明拓扑缠结或构象分布正确。
- 同一化学图可生成多个初态；不同初态用于检验准备历史敏感性，不只是重复同一构型的速度种子。
- **负例**：聚乙烯链端仍保留聚合前的离去基团，即便最小化成功也不是目标模型；短链端基的验证不能直接批准长链熔体。

后续验证先从已审查的低聚物连接与构象对照开始，再进入[单链／溶液／熔体／网络分支](../scenarios/polymer_solutions_melts_networks.md)。不在本页给出通用链长、时间步或平衡时长。

## 项目边界

现有 [GAFF 导入边界](../../../src/materiasim/engines/gromacs/parameters.py)不是通用聚合物参数导入器。当前未接入上述构建工具；本页不改变已有中性小体系限制。真实材料仍须完成[模型与交互审查](../templates/specialized.md)，并冻结资产版本与来源。
