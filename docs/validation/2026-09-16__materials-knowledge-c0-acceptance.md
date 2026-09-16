# B 批通用科学知识与 C0 验证准备验收

日期：2026-09-16。对应[补充研究计划](../plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)。这是文档与定义的验收记录，不是材料模型或真实 MD 验收。

## 本次交付

新增 9 个实质专题页，扩充原有模型兼容、链统计、采样、证据、配方和工具职责页；提供 5 类可填写 C0 清单及一个非执行复杂场景示例。来源登记从 16 条增为 37 条，保留单一来源 ID；未把相同 Grossfield 论文另建重复记录。

| 工作包 | 交付落点 | 保留边界 |
|---|---|---|
| B1 | [聚合物身份与构建](../knowledge/models/polymer_identity_and_building.md) | 不含具体端基或连接参数库 |
| B2 | [单链／溶液／熔体／网络](../knowledge/scenarios/polymer_solutions_melts_networks.md) | 交联反应化学及材料协议仍需专案 |
| B3 | [生物前处理](../knowledge/models/biomolecular_preparation.md) | 核酸／糖修饰／金属中心不提供通用参数 |
| B4 | [溶剂离子](../knowledge/models/solvent_ion_models.md)及[多组分配方](../knowledge/scenarios/multicomponent_solutions.md) | 没有实现新混合溶剂或任意盐解析 |
| B5 | [固体／表面／颗粒](../knowledge/models/solid_surface_nanoparticle_models.md) | 未下载、批准或安装材料模型 |
| B6 | [界面与限域](../knowledge/scenarios/interfaces_and_confined_systems.md) | 未放开 MDP 或新增构建器 |
| B7 | [粗粒化与迁移性](../knowledge/models/coarse_graining_and_transferability.md) | 不推荐参数或时间加速倍率 |
| B8 | [界面量](../knowledge/algorithms/interfacial_observables.md)、[链统计](../knowledge/algorithms/structural_observables.md)、[数值检查](../knowledge/verification/numerical_protocol_checks.md)、[采样](../knowledge/verification/sampling_uncertainty.md) | 没有新增 analyzer 或统计服务 |
| C0 | [五份清单与示例](../knowledge/templates/specialized.md)、[证据层次](../knowledge/verification/evidence_levels.md) | 设计清单不是 accepted 证据 |
| D | [索引](../knowledge/INDEX.md)、[知识映射](../knowledge/governance/migration_map.md)、[来源](../knowledge/references/sources.json)及指南／计划导航 | 没有 RAG 服务或自动科学批准 |

## 来源审查和未决项

- GROMACS 2025.0 与页面显示 2026.3 的引用分别登记；没有声称它们就是本地安装版。
- Auhl 由方案级摘要初查补至作者预印本的模型与内部链结构相关段落；没有把珠簧参数外推到真实聚合物。
- Grossfield 复用已有主文登记，补查块平均段落；没有复制论文图表或复现数据。
- Martini 3 和 Joung–Cheatham 的材料结论仅采用摘要可支持的范围；具体主文／SI／参数审查仍需在 C1 完成。INTERFACE 只核对仓库说明，未核验下载资产及许可。
- IUPAC 定义通过检索取得官方条目文本；直接页面访问受限已记录。表面过量的粒子数／面积形式明确为本地单位改写。
- PDF 主要依据可访问文本定位；截图未得到可核对图像，不声称图表视觉核验完成。未审材料 SI 与原数据的项不作为参数推荐。
- 当前版工具说明、公式定义与本地设计建议分开；没有用来源覆盖不到的细节填写生产数值。

## 人工检索演练

从索引进入下列页面，并核对正文是否给出问题的实际回答，而不只是一个工具名。

| 问题 | 定位和核对结论 |
|---|---|
| 聚合物端基未知怎么办？ | 聚合物身份页：停止猜测身份和连接参数；不能只推荐 polyply |
| 同一离子换水模型能直接用吗？ | 溶剂离子页：匹配与参数适用性需重审；没有推荐未核查数值 |
| 颗粒换表面修饰算同一模型吗？ | 固体表面页＋证据页：模型身份、交叉作用和受影响基准重审 |
| 固液界面一律 3dc＋NPT 吗？ | 界面页：几何、压力自由度和长程处理分开判断 |
| 接触上升能说明吸附自由能改善吗？ | 界面量页：不能，接触／区域载量／表面过量／自由能有不同定义 |
| CPU 短测通过还差什么？ | 能力矩阵＋四层证据：采样、模型与 Linux/GPU 验收不随之完成 |

这六项为人工文档检索检查，不是自动检索评测、专家认证或 MD 实验。

## 检查记录

从 MateriaSim 根执行：

```sh
zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests/unit -p 'test_documentation.py' -v
git diff --check
```

结果：5 项测试全部通过，覆盖本地链接、元数据、稳定 ID、来源与索引关系、技能边界和无效元数据拒绝；空白检查无报错。知识目录、新计划及本次记录另逐个执行 `git diff --no-index --check /dev/null <文件>`，共 32 个文件无空白错误。无输出而返回 1 的差异状态不作为空白错误。

另通过工具运行了下面 7 个简单算术断言（绝对容差 1e-12）；只检查公式表达与手算答案一致，未实现或测试任何 MD 分析器：

| 表达 | 输入 | 结果 |
|---|---|---|
| 数均摩尔质量 | 两种链各一条，质量 100、200 g/mol | 150 g/mol |
| 质量平均摩尔质量 | 同上 | 166.6666666667 g/mol |
| 摩尔质量分散度 | 同上 | 1.1111111111 |
| 独立等长块的均值 SE | 块均值为 1、3 | 1，与原量同单位 |
| 逐帧密度平均 | 两帧数量 2、4，体积 1、4 nm³ | 1.5 nm⁻³；不等于平均数除平均体积的 1.2 |
| 双界面面积归一化 | 总数 12、体相密度 1、液相体积 10、两面总面积 4（nm 单位） | 0.5 粒子/nm² |
| 两等质量点的 Rg | 点间距离 2 nm | 1 nm |

人工量纲核对同时检查了离子强度的浓度口径、持久长度的键数／长度区别、动能使用 kB 或摩尔单位 R 的区别。理论适用性仍以页面条件及后续专业复审为准。`git diff --name-only -- src catalog studies examples pyproject.toml` 无输出，未改变运行与资产边界。

## 不属于本次结果

未改模拟源码、模型参数、依赖、运行 schema 或用途政策；未安装候选工具、运行 MD／GPU、创建材料批准记录，也未提交或推送 Git。保留开始前已有未提交改动。

C1—C4 等待具体体系、目标性质、模型来源与计算预算。B 通用参考首版＋C0 可以验收，不等于全部 B/C 研究计划或复杂材料模拟能力已经完成。
