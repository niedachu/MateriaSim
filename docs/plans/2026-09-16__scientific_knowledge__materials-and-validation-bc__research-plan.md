---
{
  "type": "work_plan",
  "status": "active",
  "plan_kind": "research-plan",
  "owner": "MateriaSim",
  "module": "materiasim",
  "domain": "scientific_knowledge",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "canonical": true,
  "doc_id": "materiasim.plan.scientific_knowledge.materials_and_validation_bc",
  "source_path": null,
  "supersedes": [],
  "superseded_by": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans",
    "materiasim.plan.multicomponent_multiscenario.implementation",
    "materiasim.plan.execution.cpu_gpu_runtime"
  ],
  "related_kb": [
    "materiasim.kb.models.force_field_compatibility",
    "materiasim.kb.verification.evidence_levels",
    "materiasim.kb.verification.sampling_uncertainty",
    "materiasim.kb.platform.capabilities"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py",
    "src/materiasim/engines/gromacs/parameters.py",
    "src/materiasim/engines/gromacs/mdp.py",
    "src/materiasim/analysis/registry.py",
    "src/materiasim/specs/purpose.py",
    "tests/unit/test_documentation.py"
  ],
  "rag_exclude": true,
  "scope": "知识库 B 批材料与场景专题、C0 验证准备及 C1—C4 具体研究证据的补充研究计划",
  "implementation_status": "B0、B1—B8 通用参考首版、C0 与 D 已完成；C1 已获准取得乙醇候选参数和 NIST 数据并完成文件级初查（第 17 节），电荷精度／压力口径及模型审查未完成；C2 已交付整盒密度分析，乙醇构建与短测未完成；C3—C4 未进入。未启动新 MD、安装依赖或改力场。"
}
---

# 材料与场景知识、科学验证证据：B/C 批补充方案

## 1. 结论与范围

**2026-09-16 执行更新：B 批通用参考首版＋C0 已交付；用户已选择乙醇＋水路线，C1 在推进，C2 的密度分析先行落地，C3—C4 未进入。** 不需要现在确定最终课题，但也不能在没有模型和计算结果时完成科学验证。当前计划仍为 active；B/C0 交付见第 14 节，后续执行见第 16 节。

本方案补充[知识与计划治理方案](2026-09-16__docs_governance__scientific-knowledge-and-work-plans__governance-plan.md)第 8 节的 B/C 批，不推翻已交付的 A 批与 P0—P4，也不替代[材料功能实施计划](2026-09-14__multicomponent-multiscenario__implementation-plan.md)。知识建设负责说明为什么、何时适用、如何验证；功能计划负责把受支持的工具与场景真正接入。

| 部分 | 现在能交付什么 | 不能宣称什么 |
|---|---|---|
| B：通用科学参考层 | 材料身份、模型选择、构建与协议分支、分析定义、风险与来源 | 已有所有材料参数；所有组合可运行 |
| C0：验证准备层 | 验证设计模板、基准选取规则、证据要求、失效与复审规则 | 已取得模型验证结果；已批准 production |
| C1—C4：具体研究证据层 | 选定体系后，审模型、补必要接入、实际验证、归档结论 | 以文献结论代替本项目复现；以短测代替充分采样 |

最初调研轮只创建本计划与导航；B＋C0 执行轮仅完成文档。用户随后授权按推荐体系继续，第 16 节记录新增分析实现；仍未安装工具、调整力场、启动新 MD、创建模型或 accepted 审查文件、commit/push。下文保留任务设计与原始调研范围，当前工作状态统一见第 9 节。

## 2. 本次调研带来的关键设计判断

以下区分来源直接支持的事实与面向 MateriaSim 的设计推论。引用阅读范围见第 12 节，不把摘要阅读写成全文／SI 复核。

### 2.1 材料构建、参数赋值和体系平衡必须分开

polyply 将参数生成与坐标构建分为不同步骤；参数生成依赖已有残基块和连接规则。mBuild 侧重组件与连接，Foyer 侧重基于化学环境的原子类型与力场应用。[polyply 论文](https://www.nature.com/articles/s41467-021-27627-4)、[mBuild 文档](https://mbuild.mosdef.org/en/stable/)、[Foyer 文档](https://foyer.mosdef.org/en/stable/)

**项目推论**：知识页必须分别回答“化学结构是否正确”“参数是否完整与相容”“坐标是否可作为起点”“目标性质是否充分采样”。不能把工具成功生成文件作为后三项的答案。

### 2.2 聚合物熔体不能只用短时间密度稳定来验收

Auhl 等针对长链模型指出，某些快速引入排斥作用的准备方式会造成局部链形变，其松弛有长时间尺度。本文不能被外推为所有真实聚合物都采用同一种准备算法。[作者预印本摘要](https://arxiv.org/abs/cond-mat/0306026)

**项目推论**：聚合物专题至少拆分化学身份、初始构象、链内统计、链间结构及目标量采样；单链、熔体、溶液、交联网络不能只共享一份 NVT→NPT 配方。

### 2.3 生物大分子与粗粒化需要独立的审查分支

GROMACS 的 `pdb2gmx` 有端基、质子化和链合并等处理规则；它不是无需残基参数库的任意分子参数生成器。[GROMACS 2025.0 文档](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-pdb2gmx.html)

Martini 3 是特定粗粒化力场体系；martinize2 的蛋白工作流还涉及二级／三级结构处理和弹性网络，网络的作用单元可改变跨链连接。[Martini 3 论文](https://www.nature.com/articles/s41592-021-01098-3)、[martinize2 基本流程](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/basic_usage.html)、[弹性网络说明](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/elastic_networks.html)

**项目推论**：不能把 AA→CG 当文件格式转换，也不能把弹性网络约束下的稳定构象当作无偏折叠证据。是否保留结构、哪些结构单元受约束，要与研究问题一起审查。

### 2.4 纳米颗粒／固相需要“表面化学＋相互作用模型”，不只是几何

pymatgen 的 slab API 处理晶面、厚度、终止面和断键筛选等结构问题；INTERFACE 维护者提供针对特定无机材料及表面状态的模型。[pymatgen surface API](https://pymatgen.org/pymatgen.core.html#module-pymatgen.core.surface)、[INTERFACE 官方仓库](https://github.com/hendrikheinz/INTERFACE-force-field-and-surface-models)

**项目推论**：结构生成器不替代力场；“二氧化硅”“金属颗粒”这样的名字不足以唯一确定模拟模型。晶型、晶面、尺寸、终止、修饰、电荷状态和刚性假设应进入模型身份与适用边界。

### 2.5 多组分参数不能只检查文件能否合并

Joung–Cheatham 的单价离子工作针对特定水模型优化离子参数，说明离子参数的水模型依赖性；这不是推荐把该参数族用于所有浓度和混合溶剂。[原论文摘要](https://pubmed.ncbi.nlm.nih.gov/18593145/)

LAMMPS 的 hybrid 文档明确限制不同子势间的自动混合，并指出多体作用不能任意拆成独立原子对后组合。[LAMMPS hybrid 文档](https://docs.lammps.org/pair_hybrid.html)

**项目推论**：应建立逐对相互作用审查表，但不能认为该表足以证明多体模型兼容。换引擎也不会自动解决交叉参数；不为支持固相而立即接入所有引擎。

### 2.6 工程、数值物理、采样与模型适用性是不同证据

`physical_validation` 提供积分、动能和系综检查；部分检查要求额外模拟或额外输出。它们不等于材料模型对实验的预测能力。[Merz–Shirts 论文](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0202764)、[工具指南](https://physical-validation.readthedocs.io/en/stable/userguide.html)

OpenFF Interchange 的示例用单点能量比较检查格式／引擎转换；这种做法适合作为接入验证的一环，不足以证明充分采样或实验一致性。[官方转换与验证示例](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html)

**项目推论**：沿用现有[四类证据](../knowledge/verification/evidence_levels.md)，每类分别记录通过、失败、未运行或不适用，不能只有一个“验证通过”。

## 3. 项目真实基线与必须保留的限制

2026-09-16 阅读当前源码与[能力矩阵](../knowledge/platform/capabilities.md)所得；不是新一轮运行验收。

| 现有位置 | 本次核对到的范围 | 对 B/C 的约束 |
|---|---|---|
| `src/materiasim/engines/gromacs/specification.py` | 当前原生绑定要求正交三维周期盒；盒长 3–6 nm；1–8 组分、每种 1–100；不支持显式 SOL 模型和 CG | 这些是工程子集限制，不是 MD 的普遍物理上限 |
| `src/materiasim/engines/gromacs/parameters.py` | packing 仅接受受限显式 GAFF 拓扑；固定函数形式、排除和 defaults；总溶质原子数不超过 2000，显式组成需中性 | 外部工具产出的蛋白／聚合物／材料拓扑不能保证直接导入；不能删除检查来冒充支持 |
| `src/materiasim/engines/gromacs/mdp.py` | MDP 白名单；steep/md、三维周期；dt ≤ 0.002 ps；reviewed 输出策略关闭全精度位置／速度／力流 | slab 修正、退火、拉伸等需逐项接入；某些物理验证需要先补输出契约 |
| `src/materiasim/analysis/registry.py` | 仅登记 `hydration_contacts` 与 `component_contacts` | RDF、MSD、链统计、界面分析、科学统计尚不是现成请求 |
| `catalog/`、`studies/` | 已有 ZIL、CAT/ANI 资产与工程研究示例 | 不能当作生产级材料库；新模型来源与证据须独立审核 |
| `src/materiasim/specs/purpose.py` | 非 smoke 要求目标、环境及证据身份；production 拒绝 engineering_only 组合 | 本地声明和哈希不是科学认证或鉴权；知识页不能自动生成 accepted |

保留现有执行、冻结、恢复、预算和研究批次核心，不因本方案重建运行器。CPU 做适用的小规模检查；Linux/GPU 和长任务仍按[执行资源计划](2026-09-14__execution__cpu-gpu-runtime__implementation-plan.md)单独验收。

## 4. B 批：科学知识如何组织

### 4.1 沿用现有分类，不另建“材料百科”副本

规范内容仍归 `docs/knowledge/`，参数归 `catalog/`，研究定义归 `studies/`，原始运行证据归既有显式 Run 根。知识库只存审查过的解释、条件和证据定位，不复制大轨迹、拓扑全集、受版权限制的论文或数据。

下表保存原定页面与内容契约；执行轮已按此建立 9 个实质专题并扩充既有页，实际导航见[知识索引](../knowledge/INDEX.md)，逐包交付见[验收记录](../validation/2026-09-16__materials-knowledge-c0-acceptance.md)。页面存在不代表对应功能已经实现。

| 工作包 | 拟定落点（相对 `docs/knowledge/`） | 必须写清的内容 | 完成判断 |
|---|---|---|---|
| B1 聚合物身份与构建 | 新 `models/polymer_identity_and_building.md` | 单体连接位点、端基、序列、立构、支化／环状、链长与分布；参数连接项与坐标来源 | 能区分“同名材料”和“同一模型”，能列缺失参数而不自动猜测 |
| B2 聚合物场景 | 新 `scenarios/polymer_solutions_melts_networks.md` | 单链、溶液、熔体、交联网络分支；准备历史、链尺度松弛、网络缺陷与参考状态 | 每个分支有输入清单、协议理由、观察量和停止条件 |
| B3 生物大分子 | 新 `models/biomolecular_preparation.md` | 蛋白／核酸／糖类的区别；结构缺失、修饰、质子化、端基、二硫键、辅因子；适用参数库 | 不把所有大分子塞入聚合物单体拼接；未知残基明确拒绝或转专项研究 |
| B4 溶剂与电解质 | 新 `models/solvent_ion_models.md`；扩 `scenarios/multicomponent_solutions.md` | 水／有机溶剂／离子模型组合；数量、浓度、盐与中和；混合物目标状态和误差 | 组成可核算，参数来源与适用浓度明确，已有离子不会重复计盐 |
| B5 颗粒与固体 | 新 `models/solid_surface_nanoparticle_models.md` | 晶型、晶面、尺寸、缺陷、终止、修饰、表面电荷；刚性／约束／可变形；势函数与引擎条件 | 几何生成、表面化学、势函数和交叉作用各有独立审查项 |
| B6 界面与非均匀场景 | 新 `scenarios/interfaces_and_confined_systems.md` | 颗粒分散、固液界面、液液界面、薄膜／限域；法向、边界、电场处理和盒形自由度 | 不对所有界面套用同一 PBC／压力耦合；能说明分析区域定义 |
| B7 分辨率与工具路线 | 新 `models/coarse_graining_and_transferability.md`；扩 `platform/configuration_components.md` | AA、联合原子、CG；映射、结构偏置、跨分辨率与时间解释；各工具输入输出和限制 | CG 作为独立模型选择，不把 AA 参数直接复用或默认混用 |
| B8 分析与验证 | 扩 `algorithms/structural_observables.md`、`verification/sampling_uncertainty.md`；新 `algorithms/interfacial_observables.md`、`verification/numerical_protocol_checks.md` | 链构象、分布、扩散、吸附定义；数值与采样验证；数据要求和反例 | 公式、单位、选择、PBC、统计假设及未实现状态可追溯 |

首轮优先 B1/B4/B5 与兼容性知识，随后 B2/B3/B6/B7/B8；不同材料的阅读可穿插，但不能先写无来源的结论再补引用。

### 4.2 每个科学页面的内容契约

复用[公共模板](../knowledge/templates/knowledge.md)和[专属字段](../knowledge/templates/specialized.md)，正文至少包含：

1. 研究问题、适用材料／状态／分辨率、明确不适用范围。
2. 化学或数学定义；涉及算法时给公式、单位、输入／输出及估计对象。
3. 可选方法及选择条件，说明为何不同场景分支不同。
4. 来源支持的结论、项目设计推论、尚待验证的假设分别标记。
5. 上游工具提供什么；MateriaSim 已实现什么；仍缺参数、代码或证据中的哪一种。
6. 如何验证，以及一个不能据此得出的结论或典型失败案例。
7. 来源版本、定位、阅读范围；代码／资产／证据链接及复审触发条件。

不要求所有页都有公式；但算法页不能只有文字介绍和包名。状态沿用现有 `review` 四个维度，不额外创造冲突状态机。

### 4.3 需要优先补的算法知识，而非底层算法重写

| 主题 | 知识与接入必须确认 | 不能混淆 |
|---|---|---|
| 链尺寸／链内统计 | 质量或几何权重；链身份和骨架选择；完整分子重建；端到端、回转半径、链内距离的平均方式 | 一次生成的构象符合预期，不等于平衡分布正确 |
| RDF／分布 | 配对集合、自配对处理、壳层和密度归一化、体相假设；界面优先定义空间分区 | 均匀体相 RDF 的归一化不能无审查套在表面附近 |
| 扩散与 MSD | 跨周期位移、原子或分子质心、漂移处理、拟合窗口、方向和有限尺寸 | 拟合一段曲线不自动证明已到扩散区；CG 时间不默认等于实验时间 |
| 吸附与接触 | 接触按原子／分子还是位点计数；距离、区域、持续时间；表面面积和参考体相 | 当前接触计数不是吸附自由能；停留时间也不是接触数平均 |
| 数值／物理检查 | 守恒量适用条件、步长比较、约束与自由度；动能分布或相邻状态系综检查的输入 | 不能用普通 NVT/NPT 总能量漂移套用 NVE 守恒判据 |
| 采样与统计 | 观察量特定的平衡窗口、相关性、有效信息、重复间差异、区间估计 | 帧间标准差不是均值置信区间；更多输出帧不等于更多独立样本 |

这些是拟补的知识验收清单，具体推导从[现有观察量知识](../knowledge/algorithms/structural_observables.md)、[采样知识](../knowledge/verification/sampling_uncertainty.md)及其原始来源展开。罕见事件、自由能、增强采样、流变和反应动力学仅先写需求识别与转交条件；实施前另做专项方法调研，不能顺带声称已支持。

### 4.4 交联网络单列，而不是“多几条链”

拟补内容包括：反应位点与化学产物、交联规则、转化率、环与悬挂链、跨 PBC 连通性、干态／溶胀态参考以及批间网络差异。这是需要研究并记录的模型选择清单，不代表已有通用生成算法。

首版只形成方法决策与文献路线。特定交联化学的参数、形成历史及力学实验对应关系，必须在 C1 对该化学体系补主文／SI 调研。预先给定静态网络、按规则离线连键、真正反应 MD 是三种不同任务，不能相互冒充。

## 5. 开源组件接入策略与 GROMACS 边界

下表全部是选型建议；除当前已有 GROMACS／Packmol 子集外，不表示已安装或已接入。

| 需求 | 候选上游 | 我们需要负责 | 本轮不做 |
|---|---|---|---|
| 已参数化组分装配 | Packmol、GROMACS solvate/genion | 单位、身份、数量、拓扑顺序、几何/PBC 检查、配方核算 | 重写 packing 优化器 |
| 聚合物连接与初态 | polyply；必要时 mBuild/Foyer | 材料规则、受支持参数库、连接验证、原子映射、版本冻结 | 以“自动生成”掩盖缺失的连接参数 |
| 生物分子拓扑 | pdb2gmx；CG 分支评估 martinize2 | 前处理决策、残基覆盖、异常处理、限制与证据 | 自动猜未知残基或替换质子化选择 |
| 新小分子参数与转换 | OpenFF Toolkit／Interchange 等 | 化学身份、电荷方案、覆盖检查、转换前后语义和能量核对 | 把 OpenFF 当无机表面通用力场 |
| 晶体／表面结构 | pymatgen；匹配的已发表材料模型 | 晶胞与坐标单位、终止、电荷、表面资产、映射 | 用结构生成代替参数化 |
| 数值物理验证 | physical_validation | 输出需求、单位与自由度、适用检查、报告和失败解释 | 重写上游统计检验；自动认证模型 |
| 链与界面分析 | GROMACS 已有分析工具、合适的轨迹分析库 | 选择与估计器语义、测试、来源及平台封装 | 只因文档列出工具就增加空 analyzer |
| 多体势／反应性等超出当前路径 | 按具体势函数评估其他引擎，如 LAMMPS | 先写需求和兼容边界，再决定新后端 | 为“未来可能用”立即扩引擎 |

两项直接影响配方与场景设计的上游边界：

- `genion` 通过替换溶剂加入单原子离子；`-neutral` 是额外中和；`-conc` 不扣除已经存在的离子。因此混合物最终组成必须由平台重新核算，不能只保存一个目标浓度。[GROMACS 2025.0 genion](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-genion.html)
- `ewald-geometry=3dc` 是带 z 向修正的三维倒空间求和，用于特定 slab 几何的近似处理；它不是“所有固液界面必须打开”的开关。当前项目尚未开放该选项。[GROMACS 2025.0 MDP](https://manual.gromacs.org/documentation/2025.0/user-guide/mdp-options.html#ewald-geometry)

Packmol 文档现有正交 PBC 和区域约束能力；它提供起始坐标，不是平衡计算。B 批记录能力与版本条件，未来适配时仍核对实际安装版，不照抄动态手册选项。[Packmol 用户指南](https://m3g.github.io/packmol/userguide.shtml)

每个候选接入决策先形成一张文档表：版本／许可、输入格式及单位、化学信息保真、可表达的势函数、导出限制、失败语义、最小对照、对应源码边界。仅在真实需要出现时实施一个最小闭环，不一次装齐整个工具链。

## 6. C0：现在就能准备的验证设计

### 6.1 复用既有模板，补五种可填写清单

扩充 `docs/knowledge/templates/specialized.md`；方法说明写入现有 verification 页面。不是新增可执行 JSON schema，也不是制造已有模型的“通过记录”。

| 清单 | 必填项 |
|---|---|
| 模型审查 | 化学身份、结构／参数来源、版本与哈希、参数化方法、缺失项、分辨率、适用性质／条件、许可 |
| 相互作用审查 | 各组分模型、自作用与交叉作用来源、组合规则、1–4／排除、长程及截断约定、电荷与水／离子相容性；多体作用的整体覆盖 |
| 场景与协议设计 | 组成口径、初始与实际数量、边界／盒形、约束对象、阶段及状态交接、观察量、必需输出与预算 |
| 基准与统计设计 | 要证实／证伪的主张、参照数据及条件、训练／拟合与独立验证区分、指标单位、预定容差依据、窗口／重复／相关性方法 |
| 证据与复审 | 代码／环境／输入身份、Run 与分析定位、各层结果、失败与例外、适用范围、变更触发项、审查人和日期 |

先提供带解释的填写说明和明确标注的非执行教学示例；真实参数数值保持未决，不能用演示值悄悄建 catalog。

### 6.2 选基准的规则

候选基准必须同时满足：化学身份可确定、主文与必要参数／数据可获得、许可允许使用、状态条件清楚、存在可比观察量、规模可承受、能解释所检验的假设。

没有可比实验时，可用公开参考实现或论文数据做**实现一致性／文献复现**；这不等于独立实验验证。用同一数据拟合并评估，必须标记为拟合再现，不能称独立验证。

容差需结合参考不确定性、模型近似、数值误差和研究用途预先说明，不设置全项目统一的“误差小于 5%”。若不存在合理阈值，先标为描述性比较；不能跑完后调整标准获得通过。

### 6.3 最小实验层级

按研究需要选择以下层级，不规定每个课题都跑全套：

1. **局部模型／转换检查**：身份、拓扑、单位与参数覆盖；同一构象的能量分项，必要时力；记录函数形式差异和数值精度。
2. **单组分或基础环境**：目标溶剂、体相固体、单链等，核查所依赖的基础性质。
3. **关键二元组合**：聚合物–溶剂、表面–溶剂、小分子–表面等，针对最关键交叉作用建立对照。
4. **完整混合体系**：检验竞争吸附、聚集或其他多组分目标；必要时增加中间三元组合。

逐级通过有助于定位错误，但二元一致性不保证复杂混合物性质正确；最终研究主张仍需完整体系证据。

### 6.4 四类验证的具体产物

| 类别 | 预先设计的检查 | 最低报告要求 |
|---|---|---|
| 工程贯通 | 构建、预处理、短任务、异常拒绝、恢复、输入输出身份 | 命令与版本、真实日志、输入／结果哈希、失败信息；不得只写 exit code=0 |
| 数值／物理 | 根据算法选择步长、精度、约束或系综检查；按需附加验证计算 | 为什么适用、用了哪些数据、误差指标和差异解释；不适用项说明理由 |
| 采样质量 | 多初态／重复、窗口敏感性、慢观察量、相关性和区间估计 | 不删掉不利重复；记录预热剔除理由、相关处理及未采样到的过程 |
| 模型适用性 | 目标条件下与实验／可靠基准比较，考察相关性质与尺寸／条件变化 | 明确何种材料、范围和性质得到支持；失败、偏差和外推限制同样归档 |

采样建议参考 Grossfield 等的最佳实践，但统计区间不包括所有力场系统误差，具体方法须在正式页面补读对应章节。[论文入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC6286151/)

## 7. C1—C4：选定体系后如何形成证据

### C1：冻结研究问题与候选模型

开始前由用户或研究负责人确定：材料的化学身份、组成与条件、场景／边界、目标性质、模型分辨率、参照对象、精度需求、可用算力与预算。模型方案可以由调研提出，但不能默认为生产批准。

产物：具体研究设计、来源审查、参数缺口、交叉作用审查、功能阻塞清单。若缺少决定研究结论的参数且无可靠来源，停止该路线，提出需要的新参数化或实验依据，不随意调到“能跑”。

### C2：接入最小受支持组合并做工程／数值验证

在[材料功能计划](2026-09-14__multicomponent-multiscenario__implementation-plan.md)中承接必要代码任务：模型导入、场景构建、输出、分析或资源限制。每一项都绑定实际模型和测试，再更新能力矩阵。

新拓扑导入需审查宏／include、全局 defaults、函数形式、原子与分子映射等；不能把复杂拓扑强行裁剪成当前 GAFF 子集。外部格式转换先做相同输入的语义核对，必要时比较能量／力，不要求混沌轨迹逐帧相同。

CPU 上的小量跑通仅支持工程结论；GPU 上另做环境、输出、续跑及数值／统计一致性检查，不能把 CPU 通过直接标成 GPU 验收。

### C3：采样与模型适用性验证

执行预先设计的重复、窗口、对照和基准比较。是否延长计算由慢观察量、有效信息、差异与预算共同决定，不以固定 ns 数量判定全部材料平衡。

采样不足时申请追加或改变研究设计；模型不适用时形成新模型版本并重新审查。不要通过随意改变电荷、交叉作用或只保留有利重复得到想要的结论。

### C4：证据归档与有限范围回写

原始 Run 不可变；新分析保存新身份。知识页写结论摘要与可定位证据，catalog 保存模型资产，studies 保存研究定义，不互相复制成为第二份主版本。

审查声明必须绑定具体材料／模型版本／条件／性质和失败边界。沿用用途规则，人工审查后才决定是否形成相应证据；本方案不创建自动批准服务。

## 8. 复杂场景示例：聚合物＋颗粒＋小分子＋水盐

这是研究设计示例，不指定材料或推荐生产参数。

| 步骤 | 要回答的问题 | 对应知识／证据 |
|---|---|---|
| 定义 | 是研究平衡吸附、传质还是结构变化？颗粒是否允许变形／反应？ | C1 研究主张；B5/B6 适用范围 |
| 建模 | 链的端基／长度、表面修饰、溶质质子化、水／盐模型分别是什么？ | B1/B3/B4/B5；真实参数审查 |
| 相容 | 聚合物–水、颗粒–水、溶质–颗粒等作用依据是什么？ | 兼容知识＋C0 相互作用表，缺项则阻塞 |
| 组装 | 数量、电荷、浓度口径、周期镜像与重叠是否正确？ | B4/B6；结构和组成审计 |
| 协议 | 怎样松弛链和界面？哪些约束要释放？盒形能否变化？ | B2/B6；场景专属协议审查 |
| 对照 | 无聚合物、无颗粒或关键二元体系如何帮助定位作用？ | C0 预先设计，保持可比条件 |
| 分析 | 统计接触还是吸附量？如何定义表面与体相、比较重复？ | B8；分析定义＋C3 采样与基准 |
| 归档 | 哪个条件下支持哪个结论，还有什么没有证实？ | C4；有限适用范围的证据摘要 |

即使上述知识页全部完成，这个场景也仍需真实材料资产、当前缺失的接入能力和实际验证，不能宣称已成为任意组合的一键流程。

## 9. 实施顺序、交付与完成标准

这是本补充计划的唯一工作项状态表；索引只导航，不重复维护执行状态。

| 阶段 | 后续工作 | 交付与验收 | 当前状态 |
|---|---|---|---|
| B0 来源审查 | 复用来源登记；补主文／SI／版本核对及冲突记录 | 每项实质结论有准确来源、定位与阅读范围；摘要不足的结论不升级 | 通用结论范围完成；特定模型主文／SI／参数和数据复核仍转 C1，详见来源限制 |
| B1—B8 科学专题 | 按第 4 节逐项写实质内容并关联现有知识 | 8 个工作包都有决策、限制、工具边界和反例；未覆盖专门化学明确转 C1 | 通用参考首版完成；9 个新增页及既有页扩充 |
| C0 验证准备 | 扩模板和 verification 页，设计分层基准与复审规则 | 无具体体系也能生成明确待填清单；不能产生伪造通过证据 | 完成五类清单、非执行示例和验证设计 |
| D 文档收口 | 同步来源／索引／知识映射；检索演练与静态 QA | 下述演练和现有文档测试通过，保留专业复审限制 | 完成；六项检索演练、五项文档测试及空白／数学自检 |
| C1 具体研究立项 | 选材料、模型与问题，完成资料和参数审查 | 主张、基准、条件、预算及模型缺口明确 | 已获准取得乙醇参数／许可／NIST 数据，文件级初查完成；电荷精度、压力冲突、模型／协议／预算未审结，见第 17 节 |
| C2 受支持实现与短验 | 补必要适配并运行获准的工程／数值验证 | 真工具结果、异常拒绝、版本身份及限制明确 | 部分完成：密度／体积分析和 Mac 原生提取已通过；乙醇模型、精确配比构建和新 MD 尚未完成 |
| C3 科学验证 | 采样、独立对照和模型适用性评估 | 每个目标性质有可复核证据或明确失败／不足 | 尚未进入 |
| C4 回写与归档 | 审查证据、限定结论范围、回写规范知识 | 原始证据可定位、适用范围清楚、变更触发有效 | 尚未进入 |

**可一次连续推进的范围是 B0、B1—B8、C0、D 的文档工作**；遇到全文不可得或科学冲突时，相关子项保持未决，不以页数凑完成。C 批每个实际研究单独验收，不承诺一次计算覆盖所有材料。

完成状态要按范围表达：“B 批通用参考首版＋C0 已完成”是文档首轮交付；C1/C2 现在有局部进展，但“B/C 全部完成”仍不成立。计划维持 active，不因文档或分析接入收口而宣布材料科学验证完成。

## 10. QA、风险与复审

### 10.1 文档验收

后续改动沿用现有文档单元测试；不添加依赖来完成 Markdown 检查：

```bash
zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests/unit -p 'test_documentation.py' -v
git diff --check
```

命令从 MateriaSim 根运行。第一条核查链接、元数据、稳定 ID、来源与索引等，不验证科学正确性；第二条对未跟踪文件的覆盖有限，新文档另检查内容与空白。

人工检索演练至少包括：

- 未知聚合物端基：能否找到缺失身份／连接参数，而不是仅推荐 polyply？
- 同一离子换水模型：能否说明需要重新核对匹配，且不直接推荐参数数值？
- 颗粒换表面修饰：能否明确模型身份与交叉作用证据需要复审？
- 固液界面：能否区分边界、电场处理与压力耦合，而不是一律 3dc＋NPT？
- 接触计数上升：能否指出不足以宣称吸附自由能变好？
- CPU 短测通过：能否明确采样、模型适用性和 GPU 都没有随之验收？

### 10.2 来源与模型变更触发

| 变化 | 必须复审的范围 |
|---|---|
| 端基、立构、质子化、交联或表面修饰改变 | 化学身份、参数、构建及受影响基准 |
| 力场版本、水／离子组合、电荷方案、交叉项改变 | 相互作用与目标性质适用性；不能当普通配比调整 |
| AA/CG 或结构偏置改变 | 模型定义、观察量可比性、时间解释和验证路线 |
| 温压、浓度、相态、几何或尺寸超出已验证范围 | 场景与采样设计、有限尺寸／迁移性检查 |
| 引擎／导出器／硬件／精度改变 | 格式和数值检查、环境身份及相关适用性复审 |
| 选择、窗口、归一化、统计方法改变 | 新分析记录与结论审查，不改旧 Run |

### 10.3 明确暂缓的内容

任意反应网络、普适自动参数化、极化／恒电势／量子计算、通用增强采样、自动文献 RAG、自动科学批准、所有引擎接入均不是本轮范围。若研究目标依赖它们，先立专项计划；不能只加配置选项假装支持。

## 11. 对项目文件的预期改动与知识提取

| 位置 | B＋C0 后续动作 | 不做的事 |
|---|---|---|
| `docs/knowledge/models/`、`scenarios/`、`algorithms/`、`verification/` | 第 4 节实质专题与现有页扩充 | 不复制成研究包内第二套规范知识 |
| `docs/knowledge/references/sources.json` | 合并去重登记本次可用来源；补定位、阅读范围、局限与版本 | 不把访问失败标成已读；不把维护分支当固定版本 |
| `docs/knowledge/INDEX.md`、`governance/migration_map.md` | 同步新增页和从本计划提取的稳定内容 | 不把计划草稿当 current 科学结论 |
| `docs/knowledge/templates/specialized.md` | C0 的可填写设计清单 | 不直接改变运行 schema |
| `docs/guides/md-workflow-and-tool-boundaries.md` | 增加专题导航，保持流程入口角色 | 不重复整套科学正文 |
| `docs/plans/` | 本计划维护执行状态；功能接入仍由材料主线承接 | 不修改旧验收数字、不把 GPU 验收划掉 |
| `catalog/`、`studies/`、`src/materiasim/` | B＋C0 无运行资产／源码变化；C1/C2 按获准研究再改 | 不预先创建虚假材料资产、虚假 Run 或空插件 |

Knowledge Extraction：B1—B8 与 C0 的规范落点已登记到[知识提取映射](../knowledge/governance/migration_map.md)；[来源登记](../knowledge/references/sources.json)维护来源记录及阅读范围（B＋C0 收口为 37 条，第 15 节续行后为 41 条），正式页关联代码和来源 ID。父计划首版历史范围不变，当前复杂材料代码和科学证据没有新增。特定模型 SI、参数、实验数据及专门方法仍列为 C1—C4 缺口。

## 12. 来源清单与实际阅读范围

查阅日统一为 **2026-09-16**。下列 R 编号仅供本计划调研定位，不是已经登记的知识库 `source_refs`；实施时检查现有登记并去重。正式知识页只从单一 `sources.json` 引用。

网页可访问不等于复现完成。本轮没有安装候选库、没有执行论文代码、没有下载并核验模型参数／轨迹，也没有逐篇完成 SI 与原始数据审计。

| 编号 | 来源与版本 | 本轮阅读范围／定位 | 可支持本计划与待补项 |
|---|---|---|---|
| R01 | Grünewald 等，2022，*Polyply*，DOI 10.1038/s41467-021-27627-4；[论文](https://www.nature.com/articles/s41467-021-27627-4) | 主文 Parameter file generation、System building、Polymer melts 相关段落 | 参数／坐标分离、块和连接规则；材料参数与 SI 未逐项核验 |
| R02 | MoSDeF，mBuild 1.4.0；[官方文档](https://mbuild.mosdef.org/en/stable/) | Overview 与组件／生态职责 | 构建工具选型；具体 recipe 接入前再审 API 与运行结果 |
| R03 | MoSDeF，Foyer 1.1.0；[官方文档](https://foyer.mosdef.org/en/stable/) | Overview、SMARTS／overrides 说明和示例 | 原子类型赋值职责；未核查任何候选 XML 参数全集 |
| R04 | Auhl 等，2003，*Equilibration of Long Chain Polymer Melts in Computer Simulations*；[作者预印本](https://arxiv.org/abs/cond-mat/0306026) | 摘要与文献信息 | 长链准备的风险提示；正式方法推荐前须补正文、模型条件和数值细节 |
| R05 | GROMACS 开发团队，2025.0；[pdb2gmx](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-pdb2gmx.html) | Description 中端基、质子化与链处理 | 生物分子前处理边界；不是任意残基自动参数化保证 |
| R06 | Souza 等，2021，*Martini 3*，DOI 10.1038/s41592-021-01098-3；[论文](https://www.nature.com/articles/s41592-021-01098-3) | 摘要、Data/Code availability | 独立 CG 力场路线；具体映射、适用性质及 SI 待补读，不输出生产参数 |
| R07 | VerMoUTH/martinize2，页面显示 0.15.1.dev79+gcfcad6ecc；[基本用法](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/basic_usage.html)、[弹性网络](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/elastic_networks.html) | 结构考虑、版本行为说明、网络作用单元 | CG 结构偏置审查；动态开发文档，接入时另锁定可用发布版／提交 |
| R08 | Joung、Cheatham，2008，DOI 10.1021/jp8001614；[PubMed](https://pubmed.ncbi.nlm.nih.gov/18593145/) | 摘要，目标水模型与优化性质 | 水–离子匹配原则；PMC 正文打开遭验证页，未获取正文／SI 参数表 |
| R09 | Heinz 等，2013，DOI 10.1021/la3038846；[文献记录](https://pubmed.ncbi.nlm.nih.gov/23276161/)、[维护者模型仓库](https://github.com/hendrikheinz/INTERFACE-force-field-and-surface-models) | 文献检索摘要与书目信息；仓库 README 的材料覆盖和表面模型说明 | IFF 为候选来源；未审论文全文、下载包、许可及特定格式兼容性 |
| R10 | pymatgen，文档显示 2026.7.27；[surface API](https://pymatgen.org/pymatgen.core.html#module-pymatgen.core.surface) | Slab／SlabGenerator，晶面、单位、终止、极性与 get_slabs 说明 | 几何审查项；无本地 API 测试，动态文档需版本固定 |
| R11 | GROMACS 开发团队，2025.0；[MDP options](https://manual.gromacs.org/documentation/2025.0/user-guide/mdp-options.html#ewald-geometry) | ewald-geometry、wall-ewald-zfac 相关说明 | slab 修正边界；不据此制定所有界面协议 |
| R12 | GROMACS 开发团队，2025.0；[genion](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-genion.html) | Description、conc、neutral、Known Issues | 中和／额外盐与已有离子的计量边界 |
| R13 | Packmol 维护者；[用户指南](https://m3g.github.io/packmol/userguide.shtml) | Periodic Boundary Conditions、区域约束示例和起始坐标用途；页面注明 PBC 自 20.15.0 起 | 构建能力候选；本轮不核验安装版能力 |
| R14 | OpenFF Initiative；[Interchange 导出示例](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html) | 化学身份、导出和单点能量比较；示例使用 openff-2.2.0 | 转换验收设计；示例的其他引擎 switching 警告不能泛化为 GROMACS 必有同一问题 |
| R15 | LAMMPS 开发团队；[pair_style hybrid](https://docs.lammps.org/pair_hybrid.html) | 混合规则、多体作用与交叉作用限制；页面 Git Info 为 2Sep2026 | 其他引擎也有模型组合限制；未实际接入或验证 |
| R16 | Merz、Shirts，2018，DOI 10.1371/journal.pone.0202764；[PLOS 主文](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0202764) | 摘要、Introduction、Integrator validation 相关段落 | 物理验证与代码测试区别；SI／示例数据未复现 |
| R17 | physical_validation 1.0.5；[用户指南](https://physical-validation.readthedocs.io/en/stable/userguide.html)、[数据契约](https://physical-validation.readthedocs.io/en/stable/simulation_data.html) | 检查分类、相邻状态、积分检查、SimulationData／单位与速度数据要求 | C0 输出与验证设计；非所有检查都需要速度；未运行本地测试 |
| R18 | Grossfield 等，2018，*Best Practices for Quantification of Uncertainty and Sampling Quality*，DOI 10.33011/livecoms.1.1.5067；[论文入口](https://pmc.ncbi.nlm.nih.gov/articles/PMC6286151/) | 搜索返回的作者稿 Scope、Checklist 与误差报告段落；直接打开遭验证页 | 采样与区间估计的调研依据；不声称已通读，正式方法页需补原文对应章节 |

### 12.1 尚未完成的专业调研不能隐藏

- 特定交联反应、带电聚合物、无序蛋白、糖链／核酸修饰、表面酸碱状态等仍需专门主文与 SI；B 批先准确提供转交条件，具体模型在 C1 补齐。
- 吸附自由能、停留时间、流变、传输等必须按目标观察量补方法原文和估计条件，不能直接从接触算法扩展结论。
- 本轮尝试访问 OpenKIM 部分官方入口未成功，未用其未读页面支撑设计结论；未来若选固体势，可再核查其模型和测试资料。
- 文献可读范围、工具版本、模型下载许可和实验数据条件仍需逐项复核。调研足以划定本补充计划，但不足以批准任何具体复杂体系生产模拟。

## 13. 初始方案轮交付检查（历史）

本节只记录新计划与导航的文档检查，不作为 B/C 批执行结果。

- 已完成：方案级文献／官方文档调研、现有关键源码边界核对、新计划及导航登记。
- 检查结果：现有 `test_documentation.py` 的 5 项测试通过；`git diff --check` 无报错；新计划另用 `git diff --no-index --check /dev/null` 检查，无空白错误输出（返回 1 表示文件存在差异）。已人工复核范围、来源阅读深度和计划／能力边界；不等同独立专家科学审查。
- 未执行：B 批知识页扩充、C0 模板扩充、参数导入、MD 运行、GPU 测试、科学验收、Git 提交与推送。

## 14. B＋C0 执行轮交付检查

本节晚于第 12—13 节的初始调研记录。B0、B1—B8、C0、D 已按第 9 节限定范围交付；专业资料补读深度以来源登记为准，不回写成最初已经通读。

- 新增 9 个专题页；补充既有兼容、配方、链统计、统计误差、证据和工具职责；五类模板与复杂场景教学示例均明确非执行。
- 新增 21 条来源记录，合计 37 条；复用 Grossfield 记录并补块平均定位。Auhl 补查作者预印本；UA 补充官方参数化警告；摘要／访问受限项不升级为已审具体参数。
- 五项文档测试通过；`git diff --check` 无报错；知识目录、新计划及本次验收记录共 32 个文件另外逐个做 `git diff --no-index --check /dev/null`，无空白问题。
- 完成第 10 节六个问题的人工检索演练，以及七个公式表达的基础数值自检；这些不是 MD 或上游工具验收，也不是独立专家审查。
- 详细输入、输出与限制见[本轮验收](../validation/2026-09-16__materials-knowledge-c0-acceptance.md)。仍未执行 C1—C4、参数导入、候选工具安装、MD／GPU、生产批准和 Git 写操作。

## 15. C1 候选筛选与进入条件（2026-09-16 续行）

本轮已完成候选级检索和现有源码审查，**不是 C1 全部完成**。已向用户提出首选“乙醇＋水”，当前未收到体系选择确认；没有锁定力场、下载数据／参数包、安装工具、创建 Run 或写 accepted 证据。B＋C0 的历史交付数字保留在第 14 节。

### 15.1 为什么先建议一个二元溶液基准

以下是本地实施优先级判断，不是材料模型验证结论：

| 候选 | 能检验什么 | 当前缺口 | 首批决定 |
|---|---|---|---|
| 现有 ZIL/CAT/ANI 水体系 | 已有工程流程的回归 | 资产主要 engineering_only；本轮未取得匹配的科学基准 | 保留为回归，不把旧短测改称新科学验证 |
| 乙醇＋水 | 双组分计量、模型组合、混合／纯组分端点、密度和体积分析 | 缺乙醇冻结模型、完整兼容审查、定量配方构建及物性／统计分析 | 推荐先作为平台验收基准，待用户确认 |
| 明确端基和链长的 PEG/PEO＋水 | 聚合物连接、链身份、溶剂化和链统计 | 还需链构建／端基参数、较慢构象采样及聚合物基准 | 用户若优先要聚合物，转此路线；不同时展开两套实现 |
| 聚合物＋颗粒＋小分子＋水盐 | 完整复杂材料目标 | 同时涉及表面、交叉作用、多种构建和慢过程 | 不作为首个定位错误的基准 |

polyply 的[主文](https://www.nature.com/articles/s41467-021-27627-4)可用于聚合物工具路线参考，但本轮没有复核某条 PEG/PEO 链的参数资产。选择二元体系只限制这一批验收，不替用户确定长期课题。

### 15.2 已定位的基准和真实阅读范围

| 来源 ID | 位置和本次阅读 | 用途与限制 |
|---|---|---|
| nist-ethanol-water-density-2007 | [NIST ThermoML 文献记录](https://trc.nist.gov/ThermoML/10.1016/j.jct.2007.05.004.html)：摘要、化合物表及数据集元信息 | 原文 DOI 10.1016/j.jct.2007.05.004；覆盖 293.15、298.15、303.15 K 和 0.1 MPa，含乙醇／水密度；未下载 JSON/XML、未核读逐点数值／不确定性、原主文和 SI |
| ethanol-water-trappe-2024 | [作者稿 HTML](https://arxiv.org/html/2406.18707v1)：§2、§3.1–3.2 及相关讨论 | TraPPE-UA 乙醇与 SPC/E、TIP4P/2005 路线和密度／过量摩尔体积比较；不是本项目结果，未审参数文件和 SI |
| mosdef-reproducibility-repository | [维护者仓库](https://github.com/mosdef-hub/reproducibility_study)：README、目录入口和归档状态 | 可参考跨引擎研究组织；仓库已归档，环境与完整数据可获得性要复核；不复制其整套环境或远程同步脚本 |
| freesolv-repository | [FreeSolv](https://github.com/MobleyLab/FreeSolv)：README 的模型、资产说明和许可提示 | GAFF／AM1-BCC＋TIP3P 小分子资产候选；其水化自由能数据不是混合液密度验证，未定位并核查特定乙醇文件 |

新增 4 条单一来源记录，登记总数为 41；网页引用不是参数资产冻结。MoSDeF 相关 PMC 主文直接访问受到验证页阻挡，本轮不将检索片段视为完成主文／SI 审查，也不引用其数值结果作验收阈值。

### 15.3 已发现的两个口径陷阱

1. **组分方向**：NIST 记录中 compound 1 是水、compound 3 是乙醇；二元密度表的变量标为 Mole fraction - 1，即水的摩尔分数。若研究用 \(x_e\) 表示乙醇摩尔分数，应显式转换 \(x_e=1-x_w\)，保留原始值和转换来源。该表的 37 points 是数据集元信息，不能解释成每个温度都有 37 个浓度点。
2. **压力差异**：上述实验摘要使用 0.1 MPa，即 1 bar；2024 作者稿引言／摘要描述 0.1013 MPa，而方法段写 1 bar。不能默默将二者视为完全一致。若按实验设计，先提议 298.15 K、0.1 MPa；若要严格复现该论文，应取得输入或核清该差异，再冻结协议。

这些结论分别由上表 NIST 页面和作者稿支持。候选目标条件不是已写入生产配置的默认值。

### 15.4 模型路线尚未批准

| 路线 | 可复用依据 | 必须解决的问题 |
|---|---|---|
| GAFF／AM1-BCC＋TIP3P | FreeSolv 说明与当前 AMBER 风格导入路径较接近 | GAFF 与现有 GAFF2 类型资产不能按名字混合；需核查乙醇真实参数、库依赖、许可及混合物适用性 |
| OPLS-AA 乙醇＋经审查的水模型 | 候选开源建模生态可作为后续来源入口 | 没有完成本轮参数选择；组合规则、1–4、二面角及水模型必须一起审查，不能沿用固定 AMBER defaults |
| TraPPE-UA 乙醇＋SPC/E 或 TIP4P/2005 | 2024 作者稿有明确的混合物方法和性质讨论 | UA、其他水模型／可能的虚拟位点不在当前支持范围；参数和拓扑文件需进一步取得与核查 |

不按“当前代码最容易接受”选择科学模型，也不同时拼接三条路线。最终只锁定一条可追溯路线，再确定 C2 的最小实现范围。

### 15.5 具体到现有代码的阻塞清单

候选筛选轮重新读取了下列源码；此表保留当时待实现定位，**该轮没有修改源码**。之后的密度分析变更及剩余缺口见第 16 节。

| 文件 | 核对事实 | C2 应形成的交付／测试 |
|---|---|---|
| [specification.py](../../src/materiasim/engines/gromacs/specification.py) | 固定 TIP3P；显式 SOL 不支持；每组分 1–100，正交盒 3–6 nm | 针对获选模型明确溶剂计量和水表示；超范围继续明确拒绝，不简单删除限制 |
| [parameters.py](../../src/materiasim/engines/gromacs/parameters.py) | 显式 GAFF 拓扑、固定 AMBER defaults、有限函数与类型格式、总溶质原子数上限 2000 | 只扩获选模型需要的函数／参数语义；冲突、缺项、单位和映射均有负例，转换做数值对照 |
| [mdp.py](../../src/materiasim/engines/gromacs/mdp.py) | 白名单和阶段交接；显式采样策略；并非任意论文 MDP 都可接入 | 从审查后的方法生成受控协议，保留有效输入；不直接粘贴论文时长并运行 |
| [registry.py](../../src/materiasim/analysis/registry.py) | 只有两类接触分析 | 增补密度／体积提取及统计的明确契约；接触计数不充当混合物物性 |
| [purpose.py](../../src/materiasim/specs/purpose.py) | model_validation 需要参数、协议和验证设计证据；绑定目标与环境 | 参数审查通过后再形成真实审查文件；不能用本节候选表代替 accepted |

纯水端点在现有“至少一个显式组分、拒绝 SOL”路径中也不是可直接照抄的配置。精确浓度不能靠自动填水后假定达成；应保留目标和实际整数数量、电荷与实际摩尔分数。

### 15.6 待确认的最小验证设计

建议研究问题：“在一个已固定的非反应性模型组合下，平台能否保真构建指定乙醇／水组成，输出可追溯的密度与体积，并量化与匹配实验的偏差？”不把预期写成“必须拟合实验”。

- 第一主量：质量密度 kg/m³；次量：过量摩尔体积，仅在混合点与两个纯组分端点具有可比条件和估计器时计算。
- 组成：端点加少量实验覆盖的混合点，准确数值等逐点数据审查后确定；不是全浓度扫描。
- 纯组分端点先核查，随后混合物；纯相一致不自动证明交叉项正确。
- 由密度或体积求派生量时，明确使用平均体积还是瞬时倒体积平均；\(M/\langle V\rangle\) 与 \(\langle M/V\rangle\) 不完全相同。量纲、输出窗口和误差传播必须一致，不能混用以改善吻合度。
- 工程阶段先证明结构／计量、预处理、短轨迹与证据完整性；独立初态、生产窗口、块统计和尺寸敏感性留到获准的 C3 设计。
- 数值／科学容差尚未设定：需要参考误差、实际模型和目标用途，禁止现在填写通用百分比。
- 粒子数、步长、阶段步数、重复数、CPU 时间和存储上限未授权。本轮不把“规模可控”的建议写成已经批准的计算预算。
- 不做自由能、黏度、介电、相平衡或所有材料的通用准确性结论；这些性质需要独立方法和成本评估。

### 15.7 下一步需要的选择与授权

筛选轮提出先确认乙醇＋水或聚合物＋水；用户现已授权按乙醇＋水建议继续。参数／数据的小范围获取与许可核查仍需完成，再形成带明确规模、停止条件和预算的短测任务；依赖安装与正式长计算另按根规则授权。

Knowledge Extraction：本轮只记录候选筛选及代码缺口，没有新增稳定材料适用性结论；不另建“已验证乙醇”知识页或模型卡。来源元数据归单一登记，研究选择与执行状态仍归本计划。C1 仅完成预筛，C2—C4 未进入。

本轮检查记录：现有 `test_documentation.py` 的 5 项测试通过；`git diff --check` 无报错；本计划和来源登记另逐个执行 `git diff --no-index --check /dev/null`，均无空白错误输出（返回 1 为文件差异状态）。本轮未修改模拟源码，未运行 MD 或候选上游工具，未安装、下载数据包或执行 Git 写操作。

## 16. 乙醇＋水执行进展：先补密度分析

用户已授权按“乙醇＋水 → 短 PEG＋水 → 更复杂材料”的建议开始；本轮只推进第一体系，不并行扩展其他材料。

### 已交付的 C2 子任务

- 注册 `mass_density`：从已有封存 EDR 提取整盒密度与体积，复用 GROMACS `energy`，不新增依赖或根据坐标猜质量。
- 通过现有 AnalysisRun 和研究观察量接口；移除分发器对所有分析必须有原子映射的错误假设。现有接触分析保留原行为。
- 时间窗口显式；数据／单位／图例／时间间隔校验；保留原生输出、命令、工具版本和哈希。均值为保存帧均值，标准差不是均值误差。
- 用合成已知答案测试与现有 ZIL 水盒能量文件检验封装。**该轨迹不是乙醇体系，不能作为其科学证据。** 具体检查及外部路径见[验收记录](../validation/2026-09-16__density-analysis-acceptance.md)。未启动 MD。

### 接下来仍需完成

1. 获取与文件级核查已在随后授权轮完成，见第 17 节；主文／SI、参数精度与数据冲突仍需审查，下载不等于模型通过。
2. 从第 15.4 节候选锁定一种模型组合，不为迎合现有导入器而默选 GAFF，也不把文献模型组合的结果当成本项目结果。
3. 根据实际参数扩导入／相容检查，处理纯水端点和精确整数配比；保存目标与实际摩尔分数，不能把自动填水当精确混合。
4. 固定明确的粒子数、阶段步数、Mac CPU 总时间、存储上限与停止条件后做乙醇体系工程短测。这里的已有 EDR 分析授权不等于生产 MD 预算。
5. C3 再做平衡／独立重复／块长敏感性和实验比较；C4 才能写有限材料适用性结论。密度分析未提供自动平衡、SE/CI 或过量摩尔体积。

Knowledge Extraction：估计器与工具边界维护在[整盒密度知识](../knowledge/algorithms/bulk_density.md)；来源登记新增 `gmx-energy-2026`（共 42 条）；[能力矩阵](../knowledge/platform/capabilities.md)维护实际支持范围。此节只记研究执行与未决事项，不创建“已验证乙醇”模型卡或 accepted 审查材料。

## 17. 已授权来源获取：乙醇候选与 NIST 数据

用户确认小范围下载后，本轮仅做资料准备，不启动 MD。取得固定 FreeSolv 提交中的乙醇 GRO／TOP、身份索引和许可，以及单篇 NIST ThermoML JSON／许可页面。外部资料含清单约 0.62 MB；来源 URL、精确大小和哈希见外部 manifest，核查摘要及复现入口见[研究资料说明](../../studies/ethanol_water_benchmark/README.md)。原件未修改，未创建正式模型卡或 accepted 用途审查。

文件级初查暴露的必要后续：候选电荷合计 −0.0001 e／分子会随数量累积；参数格式、RB 二面角、零 LJ 类型和高精度 GRO 尚不被现有导入器支持；NIST JSON 压力 101 kPa 与摘要 0.1 MPa 存在口径差异。不能自动调电荷／压力或放宽检查来生成成功结果。配套水模型与研究协议仍未锁定。

本轮只形成可追溯候选资料，不把特殊来源现象上升为所有模型的通用知识，也不声称乙醇模拟已经跑通。来源获取脚本的 8 项离线测试通过，8 个已下载来源文件的大小和 SHA-256 复核通过。无依赖安装、MD/GPU 使用或 Git 写操作；C1 仍在进行，C2 组装及 C3/C4 待后续。
