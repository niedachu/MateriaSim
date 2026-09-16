---
{
  "type": "knowledge",
  "doc_kind": "governance",
  "doc_id": "materiasim.kb.governance.migration_map",
  "title": "知识提取映射",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "本批知识提取与保留关系；无文件删除或移动",
  "source_refs": [],
  "related_code": [],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "not_applicable",
    "implementation": "not_applicable",
    "evidence": "not_assessed",
    "applicability": "not_applicable"
  },
  "limitations": [
    "本地文档规则或实现范围，不是材料验证结论"
  ],
  "rag_exclude": false
}
---

# 知识提取映射

日期 2026-09-16。原文件全部保留路径；提取指稳定定义的规范维护转移，不改写旧验收事实。

| 来源 | 知识落点 | 处置 |
|---|---|---|
| MD 流程指南 §3.1–3.2 | [模型兼容](../models/force_field_compatibility.md) | 指南保留旅程概述；详细判断归知识 |
| MD 流程指南 §3.3 浓度公式 | [单位组成](../foundations/units_composition.md) | 公式与口径规范归知识，指南替换为链接 |
| MD 流程指南 §3.4、§4 | [积分](../algorithms/integration_constraints.md)、[温压](../algorithms/ensemble_control.md)、[场景](../scenarios/multicomponent_solutions.md) | 增补依据与边界，指南保留操作路线 |
| 指南分析／验收段落及现有代码 | [接触](../algorithms/contacts.md)、[统计](../verification/sampling_uncertainty.md)、[证据](../verification/evidence_levels.md) | 明确规范估计器；历史报告不回写 |
| 五份历史方案的现状说明 | [能力](../platform/capabilities.md)、[配置组件](../platform/configuration_components.md) | 提取稳定职责，未来设计保留在计划 |
| 知识治理方案的接触示例 | [接触定义](../algorithms/contacts.md) | 原计划是历史示范，不作为可独立更新的算法规范 |
| MyQuant 治理参考 | [维护规则](maintenance.md)、[计划规则](../../plans/README.md) | 采用治理思想，未复制量化知识或机器依赖 |

来源入口：[MD 指南](../../guides/md-workflow-and-tool-boundaries.md)、[计划迁移与范围核对](../../plans/MIGRATION_MAP.md)。未来更改公式只更新规范知识与实现／测试的相关部分，不同步改写历史方案。

本文件管理知识归属；计划 MIGRATION_MAP 管理计划路径和替代关系；已有 architecture/migration_map.json 的代码／资产映射不受影响。此处为本地文档处理记录，无外部科学主张。

## 2026-09-16 B 批与 C0 增补提取

来源是 [B/C 补充计划](../../plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)及本轮补查资料；计划保存执行历史，以下页面维护稳定定义。来源 ID 和阅读范围统一登记在 sources.json，不在此复制。

| 提取内容 | 正式知识落点 | 边界 |
|---|---|---|
| B1/B2 聚合物身份与场景 | [模型](../models/polymer_identity_and_building.md)、[单链／溶液／熔体／网络](../scenarios/polymer_solutions_melts_networks.md) | 没有具体聚合物参数／平衡证据 |
| B3/B4 生物与溶剂盐 | [生物前处理](../models/biomolecular_preparation.md)、[溶剂离子](../models/solvent_ion_models.md) | 未批准任何残基或盐参数组合 |
| B5/B6 固相、颗粒与界面 | [材料身份](../models/solid_surface_nanoparticle_models.md)、[场景](../scenarios/interfaces_and_confined_systems.md) | 不代表新构建器或后端接入 |
| B7 粗粒化 | [映射与可迁移性](../models/coarse_graining_and_transferability.md) | 当前运行器仍拒绝 CG |
| B8 观察量与验证 | [链统计](../algorithms/structural_observables.md)、[界面量](../algorithms/interfacial_observables.md)、[数值](../verification/numerical_protocol_checks.md)、[采样](../verification/sampling_uncertainty.md) | 规范和验收设计，不是新增分析代码 |
| C0 审查与证据设计 | [五类清单](../templates/specialized.md)、[四层证据](../verification/evidence_levels.md) | 真实记录留待 C1—C4，不制造 accepted |

本轮无文件迁移／删除，无材料资产或 Run 变更；本批检查见[验收记录](../../validation/2026-09-16__materials-knowledge-c0-acceptance.md)。

## 2026-09-16 乙醇基准准备：C2 密度分析

[B/C 方案 §16](../../plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)推进了整盒密度封装；估计器、单位及限制归[整盒密度](../algorithms/bulk_density.md)，实际覆盖归[能力矩阵](../platform/capabilities.md)，实测记录归[分析验收](../../validation/2026-09-16__density-analysis-acceptance.md)。未移动旧页面或原始结果，不产生乙醇模型的科学适用性结论。
