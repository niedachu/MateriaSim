# MateriaSim 科学知识库

本库回答“为什么这样模拟、何时适用、怎样判断结果”。**知识存在不等于平台已支持，更不等于模型已通过科学验证。** 首版是经官方资料与源码对照的参考层，不是独立专家认证。

## 从研究问题开始

| 你要做什么 | 阅读入口 |
|---|---|
| 搞清 MD 模型、系综、分辨率 | [物理基础](foundations/classical_md.md) |
| 定义配方、数量、单位与盐 | [组成与单位](foundations/units_composition.md) |
| 判断多个模型能否一起用 | [力场兼容](models/force_field_compatibility.md) |
| 选择盒子、步长和阶段 | [周期与非键](algorithms/periodic_nonbonded.md)、[积分与约束](algorithms/integration_constraints.md)、[温压控制](algorithms/ensemble_control.md) |
| 分析接触、结构与扩散 | [两类接触](algorithms/contacts.md)、[RDF/MSD/链构象](algorithms/structural_observables.md) |
| 判断有没有平衡、误差多大 | [采样与误差](verification/sampling_uncertainty.md)、[验证层次](verification/evidence_levels.md) |
| 设计多组分或复杂场景 | [溶液及复杂体系路线](scenarios/multicomponent_solutions.md) |
| 准备聚合物或生物大分子 | [聚合物身份](models/polymer_identity_and_building.md)、[单链／熔体／网络](scenarios/polymer_solutions_melts_networks.md)、[生物前处理](models/biomolecular_preparation.md) |
| 选择溶剂盐、颗粒和表面模型 | [溶剂／离子](models/solvent_ion_models.md)、[固体／表面](models/solid_surface_nanoparticle_models.md) |
| 判断 CG 或界面协议是否合适 | [粗粒化边界](models/coarse_graining_and_transferability.md)、[界面与限域](scenarios/interfaces_and_confined_systems.md) |
| 设计正式模拟前的验证 | [数值检查与输出](verification/numerical_protocol_checks.md)、[界面观察量](algorithms/interfacial_observables.md)、[C0 五类清单](templates/specialized.md) |
| 查项目实际能做什么 | [能力矩阵](platform/capabilities.md)、[配置与组件归属](platform/configuration_components.md) |
| 查资料、维护文档或安排工作 | [来源登记](references/sources.json)、[维护规则](governance/maintenance.md)、[工作计划](../plans/INDEX.md) |

所有条目见 [INDEX](INDEX.md)；操作步骤见[模拟指南](../guides/simulation.md)与[研究指南](../guides/research.md)。先找知识和能力，再决定是否需要开发或新的验证。

## 归属与状态

知识解释依据；`catalog/` 保存模型与协议资产；研究配置保存本次选择；Run 保存实际输入与结果；工作计划保存待办和历史。相互关联，不复制拓扑、轨迹或整篇论文。

科学条目的 `current` 只针对声明的参考知识范围；`review` 单列理论资料、实现、证据及模型适用性。当前科学条目均没有新增材料实测。方案和草稿默认不作为当前知识；现有项目没有 RAG 服务。
