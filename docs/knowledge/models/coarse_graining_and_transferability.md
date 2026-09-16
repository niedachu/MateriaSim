---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.coarse_graining_and_transferability",
  "title": "粗粒化、结构偏置与可迁移性",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "martini3-2021",
    "martinize2-basic",
    "martinize2-elastic",
    "polyply-2022",
    "gmx-force-fields-2025"
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

# 粗粒化、结构偏置与可迁移性

## AA→CG 是换模型，不只是少几个原子

分辨率还包括联合原子（UA），不能简单归为“删氢的 AA”。例如官方文档说明 GROMOS 的 UA 表示不显式包含脂肪族非极性氢；同时警告其部分参数化与历史双截断／积分方案有关，改变算法可能改变物性。因此本页仅解释 UA 类别，不据此推荐 GROMOS 参数。[GROMACS 2025.0 力场说明](https://manual.gromacs.org/documentation/2025.0/user-guide/force-fields.html#gromos)

本地审查要求：AA、UA、CG 都记录粒子映射、质量／电荷与函数约定；不能仅删原子保留旧参数，也不能未经说明比较不同粒子定义的 RDF 或接触。

Martini 3 是专门的粗粒化力场路线；本轮对原论文仅核查摘要及数据／代码可用性，不据此给出具体参数或普适精度保证。[原论文](https://www.nature.com/articles/s41592-021-01098-3)

本地审查要求明确以下四种不同操作：

| 操作 | 要保存的身份 | 不能得出的结论 |
|---|---|---|
| 结构映射 | 原子集合→珠子、质量／电荷与坐标定义、端基和特殊位点 | 结构映射本身已经确定力场 |
| 参数化／选择 CG 模型 | 版本、粒子类型、相互作用和目标性质、条件范围 | AA 参数合并后自然成为可用 CG 力场 |
| 结构偏置 | 弹性网络／约束的节点、连接和强度、作用单元 | 偏置维持的结构是无偏动力学预测 |
| 回映射 | 重建方式、原子身份、松弛方案、局部缺失信息 | 重建坐标自动恢复了原子级平衡分布 |

polyply 在坐标构建中的简化表示只是生成初态的算法步骤，不因此改变生产模型分辨率。[polyply 系统构建](https://www.nature.com/articles/s41467-021-27627-4)

## 弹性网络为什么需要研究级审查

martinize2 可以限定弹性连接的结构单元，包括链和指定区域。[官方弹性网络说明](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/elastic_networks.html)

本地决策：若目标是域间运动、链解离、折叠或无序构象，先检查网络是否直接限制该过程；若目标只研究保持结构条件下的环境效应，明确这项条件。不同版本的转换行为要另锁定，不能只引用 latest 文档。[基本用法与版本说明](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/basic_usage.html)

## C0 可迁移性审查矩阵

| 要外推的维度 | 至少应补的证据设计 |
|---|---|
| 温度／浓度／溶剂组成 | 目标条件对照与失效范围；不直接转用参数拟合点的误差 |
| 链长／拓扑／表面曲率 | 结构与交叉作用是否仍覆盖；必要的尺寸敏感性 |
| 分辨率 | 先把 AA 观察量映射到同一 CG 定义，再比较 |
| 时间与动力学 | 单独验证目标动态量；未验证时不指定统一时间加速倍率 |
| AA 与 CG 混合 | 明确分辨率间的相互作用与热力学一致性；普通文件拼接不构成混合分辨率方法 |

这是本地验证设计，不宣称某一模型在上述各维度已通过或必然失败。若需要反演、力匹配、相对熵等新参数化，应另读对应方法论文并立专项，不在这里给未核查的算法实现。

## 项目状态与拒绝边界

当前 [绑定](../../../src/materiasim/engines/gromacs/specification.py)显式拒绝 coarse-grained 模型。本页没有接入 CG；也没有新增未实现的配置开关。后续须同时完成导入／执行／分析语义和四类验证，而不是只放开分辨率检查。
