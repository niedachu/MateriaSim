---
{
  "type": "knowledge",
  "doc_kind": "contract",
  "doc_id": "materiasim.kb.platform.configuration_components",
  "title": "配置、组件与知识的关系",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-18",
  "scope": "五类内容与实际配置、资产、知识和计划的归属",
  "source_refs": [
    "mbuild-docs",
    "foyer-docs",
    "polyply-2022",
    "openff-interchange-export",
    "physical-validation-guide",
    "pymatgen-surface"
  ],
  "related_code": [],
  "related_assets": [
    "studies/mixed_builders_smoke/research.json",
    "catalog/models/cat_model.json",
    "examples/v3/packed_zil_water.json"
  ],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans",
    "materiasim.plan.scientific_knowledge.materials_and_validation_bc"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "not_applicable",
    "implementation": "code_checked",
    "evidence": "not_assessed",
    "applicability": "not_applicable"
  },
  "limitations": [
    "本地文档规则或实现范围，不是材料验证结论"
  ],
  "rag_exclude": false
}
---

# 配置、组件与知识的关系

## 五类不是五个材料目录

| 原分类 | 规范归属 | 本项目实例 |
|---|---|---|
| GROMACS 自带 | 算法知识解释，上游维护实现 | [积分与约束](../algorithms/integration_constraints.md) |
| 经常改的条件 | 知识解释语义，实验／研究配置记录本次值 | [单位组成](../foundations/units_composition.md)、[研究定义](../../../studies/mixed_builders_smoke/research.json) |
| 预配组件 | 模型知识解释依据，catalog 保存可执行资产 | [力场兼容](../models/force_field_compatibility.md)、[模型卡](../../../catalog/models/cat_model.json) |
| 当前已有 | 能力矩阵关联代码和证据 | [能力矩阵](capabilities.md) |
| 后续要做 | 知识说明缺口，计划管理实施 | [计划索引](../../plans/INDEX.md) |

## 已有配置如何组合

[原生 v3 例子](../../../examples/v3/packed_zil_water.json)把组分／模型、interaction_bundle、scenario、protocol、analysis_requests、execution_profile 分开。详细字段以文件与[模拟指南](../../guides/simulation.md)为准；这里不是另一个可执行 schema。

| 修改 | 应更新和复核 |
|---|---|
| 组分数、温度、链长等研究条件 | 新研究条件与组成；模型是否仍适用；平衡和采样设计 |
| 力场、电荷、端基、表面化学 | 模型身份和相容性；不能只复测程序通过 |
| 步长、约束、非键近似 | 数值与目标量检查，记录协议来源 |
| 选择、阈值、窗口、重复 | 观察量语义、比较设计和不确定性 |
| CPU/GPU、工具版本 | 环境身份、执行与数值检查；不要求轨迹逐位一致 |

这些是研究审查触发条件，不是系统自动实现的影响分析服务。

## 一条可追溯关系

2026-09-17 新增的[规则 Campaign](../../guides/harness.md)只是外层管理：`automation.json` 引用普通实验／研究定义与静态能力白名单，独立用户授权限定目录、期限与额度，manifest 冻结输入及实现，事件记录投递和管理操作。MD 状态仍归 Run，分析仍归 AnalysisRun，研究任务仍由原 research 引擎执行；侧车不能改模型、力场或用途。科学质量保持未评估；知识页不授予执行权限。

同日加固后，默认规则 Campaign contract v2 冻结真实依赖图、配置／源码及所需分析依赖版本，逐任务检查冲突；不同任务可选择不同受支持场景。暂停发生在既有 build/run/resume/analyze 操作之间，不另造数值运行器。Decision v1 仅只读校验证据；reconcile 仅对账，不投递计算。历史 v1 Campaign 保留只读，不原地升级。实测范围与故障缺口见[加固报告](../../validation/2026-09-17__harness-local-hardening.md)。

2026-09-18 的[本地 agent 协议](../../guides/harness-agent.md)新增显式策略的 Campaign v3。用户授权与 agent 策略独立冻结；agent 只读取访问留痕的进度摘要，Decision v2 引用摘要哈希、序号及期限，continue 只允许一个现有核心操作，不能改参数、追加任务或扩权。人工接管独立留痕；终态和未结算故障不能强行重开。脚本 provider 的[5 Run 验收](../../validation/2026-09-18__harness-local-agent-acceptance.md)不代表真实模型、凭据隔离或科学决策已验收。

监督连接由继承的只读管道表示，不是持久化 PID。连接消失时 worker 请求协作停止，并拒绝后续操作；已有回执仍按原事件和预算对账。双方一起丢失且无回执则保持人工审查，不用新 Run 重置预算。该本地运行保护及独立卷满盘检查见[后续故障专项](../../validation/2026-09-17__harness-crash-storage-acceptance.md)，不扩大材料或科学能力。

研究定义引用资产和分析请求 → 平台冻结实际输入 → 引擎产生阶段产物 → 独立分析生成证据 → 经审查结论链接知识；缺功能则另立计划。

知识页不能复制一套拓扑或协议参数作为新主版本。当前精确模型组合由资产哈希定位，解释性文字由知识页维护；两者冲突时保留证据并排查，不默默修改参数使之匹配。

## 工具接入决策：优先复用的边界

下表是基于官方职责的本地设计决策，**不是已安装／已实现清单**。一次只围绕实际材料需求接一个可验收闭环。

| 需求 | 可评估的已有工具 | MateriaSim 应负责 | 接入前最小检查 |
|---|---|---|---|
| 聚合物图与初态 | [polyply](https://www.nature.com/articles/s41467-021-27627-4) | 材料连接规则、参数覆盖、原子映射 | 端基、跨残基项、链身份与导入限制 |
| 组件结构／原子类型 | [mBuild](https://mbuild.mosdef.org/en/stable/)、[Foyer](https://foyer.mosdef.org/en/stable/) | 编排与输入输出审计，不重复其通用内核 | 连接语义、typing 歧义和参数库身份 |
| 新有机小分子参数转换 | [OpenFF Interchange](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html) | 化学身份和目标格式检查、数值对照 | 函数覆盖、单位、原子顺序与能量约定 |
| 表面几何 | [pymatgen](https://pymatgen.org/pymatgen.core.html#module-pymatgen.core.surface) | 晶面／终止、电荷与参数资产匹配 | Å/nm、晶胞约定、未饱和表面处理 |
| 数值验证 | [physical_validation](https://physical-validation.readthedocs.io/en/stable/userguide.html) | 输出／单位／自由度、版本与报告 | 数据是否齐全、检查是否适用 |

生物分子和 CG 的工具决策分别见[前处理](../models/biomolecular_preparation.md)与[粗粒化](../models/coarse_graining_and_transferability.md)；非现有势函数需求见[固体模型](../models/solid_surface_nanoparticle_models.md)。已有 Packmol／GROMACS 构建能力继续按[能力矩阵](capabilities.md)使用，不因上游能力更广就跳过平台校验。

接入决策还必须附：版本／提交与许可、输入格式和单位、上游成功／失败语义、当前导入边界、最小参考例、部署依赖与预算。变更依赖和增加真实运行仍需授权；本轮只交付这些决策依据。
