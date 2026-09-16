# 计划来源、路径与覆盖审计

首版审计日期 2026-09-16；备份 a044693。首版盘点的六份计划均留在原路径，无文件迁移或删除。首次统一元数据，原正文保留历史语境；当前执行状态读头部与新增审计说明。后续新增计划单列来源，不计为首版迁移。

| 来源／当前路径（相同） | 稳定 ID | 覆盖关系和未决范围 |
|---|---|---|
| [初始升级](2026-09-14__multicomponent-simulation__upgrade-plan.md) | materiasim.plan.multicomponent_simulation.upgrade | 长期蓝图；具体执行按 M1—M6；旧 upgrade-plan 文件名作为历史例外保留 |
| [多组分场景](2026-09-14__multicomponent-multiscenario__implementation-plan.md) | materiasim.plan.multicomponent_multiscenario.implementation | 已有 M1/M2/M3a；混合溶剂及后续材料未完成；旧缺 domain 分段的名称保留 |
| [CPU/GPU](2026-09-14__execution__cpu-gpu-runtime__implementation-plan.md) | materiasim.plan.execution.cpu_gpu_runtime | 原声明 draft/未实施已过时；框架 v1 已交付部分预算／执行／候选 GPU，服务器、长负载仍待验收，标 active 而非 completed |
| [包与研究](2026-09-15__architecture__simulation-package-and-research-bundles__implementation-plan.md) | materiasim.plan.architecture.simulation_package_research_bundles | A—D 历史交付，后继框架进一步覆盖契约与执行；不凭此宣布 E—F／新材料完成 |
| [框架 v1](2026-09-15__framework__extensible-core-v1__implementation-plan.md) | materiasim-framework-extensible-core-v1-20260915 | 保留原 ID 和本地完成状态；Linux/GPU、长负载、新材料和科学验证不包含在完成范围 |
| [知识治理](2026-09-16__docs_governance__scientific-knowledge-and-work-plans__governance-plan.md) | materiasim.plan.docs_governance.scientific_knowledge_and_work_plans | 本次首版建设主计划；B/C 为后续，不自动完成 |
| [B/C 补充研究](2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)（2026-09-16 新增，无迁移来源） | materiasim.plan.scientific_knowledge.materials_and_validation_bc | 承接 B 通用参考、C0 验证准备与 C1—C4 实证主线；§16–17 续行密度接入与乙醇来源获取，规范定义提取至知识映射，状态见计划；无迁移或替代 |

部分覆盖用本表及计划审计说明表达，不用 supersedes 错误宣称旧计划全部被替代；本批没有整份文档的替代／删除。source_path 保存原仓库路径，Git 保留原文头部。

稳定能力归[能力矩阵](../knowledge/platform/capabilities.md)，知识提取归[知识映射](../knowledge/governance/migration_map.md)。历史方案中的旧目录或“该文目前仅为方案”等措辞不代表当前代码，不能据此恢复旧架构。
