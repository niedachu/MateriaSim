# 科学知识库与工作计划首版验收

日期：2026-09-16。实施前备份：a044693。范围：知识治理方案 P0—P4 与 A 批参考知识；不包含 B 批深入材料专题或 C 批具体材料科学验证。

结论：P0—P4 文档首版通过本次定向检查。新增 13 篇科学／平台主题页、2 篇治理记录、知识导航与模板、16 个来源登记，六份计划统一元数据和范围审计；不表示新材料功能或科学验证已完成。

## 实际执行的检查

工作目录为 MateriaSim 仓库根，定向测试使用既有 `zwitterion_hydration_md/.venv-macos-analysis/bin/python`，未新增依赖。

| 检查 | 命令主体 | 结果 |
|---|---|---|
| 文档治理 | `python -B -m unittest discover -s tests/unit -p 'test_documentation.py' -v` | 5 项通过：链接、元数据、ID／来源／索引、非法输入拒绝及技能身份 |
| 水化几何定义 | `PYTHONPATH=src python -B -m unittest discover -s tests/unit -p 'test_analysis.py' -v` | 2 项通过 |
| 装配与分子对定义 | `PYTHONPATH=src python -B -m unittest discover -s tests/unit -p 'test_packing.py' -v` | 21 项通过；未调用真实 Packmol 或 MD |
| 两项 Skill | 已有 skill-creator 的 quick_validate.py，使用本机 `python3` | 两项均报告 Skill is valid；此解释器已有 YAML，不修改项目依赖 |
| 格式 | `git diff --check` | 通过；新增文档另核对空白与围栏 |

第一轮文档测试发现最初升级方案指向迁移前 `materials_simulation/docs/` 的失效链接。已根据现有代码／资产迁移表核实报告现位于 `docs/validation/`，只修正链接；复测通过，未修改历史报告。

没有运行全套程序回归或真实引擎模拟：本轮不改模拟实现，定向检查与范围相称。外部资料已通过网页查阅，但本地测试不保证外链永久有效；未复核历史报告中的所有仓库外原始文件。

## 科学资料核对

- 官方 GROMACS 手册核对了单位、周期、非键、积分、约束、温压控制、体系准备及 RDF/MSD/gyrate/genion 的相关段落；文档页面版本和实际阅读范围见[来源登记](../knowledge/references/sources.json)。
- Grossfield 等论文已核读期刊主文的范围说明、术语与 §7.3.1 Eqs.11–12；未完成整篇论文／SI／数据／代码复现。未将摘要阅读写成全文验证。
- PyMBAR 4.0 和 MDAnalysis 2.7 的相关 API 语义已对照；未安装或运行 PyMBAR。
- 逐项复核了 nm/Å、体积到 L、组成分母、接触去重、均值与波动、周期几何、MSD 扩散区间和 Rg 权重的文字／公式。此为 Agent 资料对照审阅，不是独立专家评审。

## 检索演练

| 问题 | 知识定位与应答边界 |
|---|---|
| GROMACS 有 RDF，项目能否直接用？ | [结构分析](../knowledge/algorithms/structural_observables.md)与[能力矩阵](../knowledge/platform/capabilities.md)：上游有，项目尚无分析适配 |
| 两套力场能否直接混用？ | [兼容审查](../knowledge/models/force_field_compatibility.md)：函数、缩放、交叉项与适用性分别审查 |
| 聚合物＋颗粒＋水盐要准备什么？ | [场景路线](../knowledge/scenarios/multicomponent_solutions.md)：身份、模型、边界、构建和分析；尚无可运行复杂配方 |
| 标准差是不是置信区间？ | [接触](../knowledge/algorithms/contacts.md)和[采样](../knowledge/verification/sampling_uncertainty.md)：不是；当前未给科学区间 |
| CPU 短测证明 GPU 和科学有效性吗？ | [证据层次](../knowledge/verification/evidence_levels.md)：不能跨层推导 |
| 改配比／步长／力场分别影响什么？ | [配置与组件](../knowledge/platform/configuration_components.md)：条件、数值近似和模型身份分别复核 |

以上是人工沿链接进行的文档检索演练，不是独立 Agent 行为测试或真实模拟。

## 保留范围

没有修改 src、catalog、研究配置、历史 Run 或科学参数；没有新增依赖、运行 MD、安装引擎、删除数据或推送。当前维护环境缺 PyYAML，不为文档新增它；机器校验明确使用 JSON frontmatter 子集，不声称解析任意 YAML。
