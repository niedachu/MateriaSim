# AGENTS.md

## Project Purpose

项目名称为 **MateriaSim**，根目录为 `/Users/niezhidong/Desktop/MateriaSim`（原名 `Machine Learning`）。当前唯一核心为 `src/materiasim/`，命令为 `materiasim`；历史报告中的旧包名与绝对路径保留为来源记录，不据此重新创建旧目录。

本工作区维护材料分子模拟平台及现有 ZIL/离子对水化案例。`src/materiasim/` 是共用工程核心，支持 ZIL/CAT/ANI 按整数数量自动装配、加水或无水周期盒短测、快照、GROMACS 运行/续跑及独立水化/组分接触分析；研究层支持显式条件与种子、冻结计划、串行批次和受限接触比较。Mac CPU 当前子集已实测，Linux 待验收。混合溶剂、聚合物、固相与纳米材料尚未支持，M3 仅完成已有模型子集。实际入口与限制以根 README 和 docs/guides 为准，不得把方案中的其他材料覆盖视为已实现能力。

Scientific traceability and reproducibility take priority over runtime and code brevity. Every conclusion must clearly distinguish among facts reported in the paper, local reproduction results, model predictions, and research hypotheses.

## Before Starting a Task

- Read the README, scripts, and data headers directly relevant to the task. Do not infer content from filenames alone.
- For paper-related questions, check the main article, Supplementary Information, and supplied data files. State which type of evidence supports each conclusion.
- Change only files required by the current request. Preserve user changes and unrelated files.
- 本工作区使用本地 Git 管理源码、测试、配置、文档与示例所需的小型冻结模型输入；不假定已配置远端或 CI。虚拟环境、轨迹和生成输出按 `.gitignore` 排除；被忽略的文件不保证存在或有备份，Git 提交不等于完整科研数据备份。历史 Run 中的旧源码状态仍以其冻结清单为准。

## 任务路由与局部规则

- 根规则管理公共工程、授权和数据边界；局部规则细化所属模块，不自行放宽数据保护或科学验收要求。
- 新模拟平台开发：读取 [src/materiasim/AGENTS.md](src/materiasim/AGENTS.md)。现有 `zwitterion_hydration_md/` 和 `ion_pair_hydration_md/` 的 MD 任务也须读取此公共模拟规则，再读取所属案例 README 和相关代码；不据此自动迁移旧目录。
- 历史方案保留当时的工作区布局与证据，不按其中的旧目录引用重新创建、恢复或下载已清理的独立项目。新增非模拟课题需另行明确范围。

### 项目内技能

以下是本项目维护的技能，按任务读取完整 `SKILL.md`；不依赖其他工作区或全局安装。仅查看/修改技能本身时，不运行其科研流程。

- 模拟研究设计、模型/案例复用、模拟结果比较或已授权的研究执行：使用 [simulation-research](skills/simulation-research/SKILL.md)。普通代码修复和纯文档整理不强制走研究流程。
- 模拟报错、异常轨迹、续跑疑问或结果可靠性诊断：使用 [simulation-diagnostics](skills/simulation-diagnostics/SKILL.md)。诊断默认只读；修复/重跑需属于用户已授权范围。
- 代码审查及影响输入、运行或分析行为的修改：使用 [审查清单](docs/ai/REVIEW_CHECKLIST.md) 的相关条目，不要求无关检查。
- 引入兼容分支、旧格式读取或迁移适配时：读取 [兼容性规则](docs/ai/COMPATIBILITY_POLICY.md)。

技能是操作指南，不替代源码、程序校验或测试；技能文档存在不表示客户端已自动发现，也不表示命令已实现。根文件的上述路由提供显式读取入口。

## Authorization Boundary

- Treat requests phrased as "explain," "how should I," "what is," "can you," "give me an outline," or equivalent wording as read-only consultation.
- Do not create, edit, move, or delete files, and do not run state-changing commands, unless the user explicitly authorizes implementation.
- “先回答”“只看方案”“诊断原因”只授权咨询与必要只读检查；“补充文档”只授权相应文档修改，不授权实施方案。
- 用户已明确授权的实现、文件新增和范围内小量验收可继续，不对相同步骤反复确认。只有范围不清或需要新的权限时，提出一个聚焦问题。
- 新增/变更依赖、修改全局环境、访问认证/付费资源、下载新数据、超出已约定预算的正式长计算、改变研究目标或科学协议、移动/删除原始数据、覆盖正式输出和 Git 写操作，需要明确授权；既有授权只覆盖已说明的具体范围。
- Before making a file change, briefly state the exact file and intended action.

## Project Layout

- `src/materiasim/`：唯一模拟核心、研究编排和命令入口；`tests/` 保存测试与验收工具。
- `catalog/`、`examples/`、`studies/`：共享模型/协议资产、最小实验、研究源码包；研究层不复制 runner。
- `materials_simulation/`：保留的历史示例与迁移指引；验收记录现归 `docs/validation/`。
- `zwitterion_hydration_md/`：ZIL 历史案例、原始模型/协议及 `.venv-macos-analysis/` 分析环境；不是可整目录删除的旧副本。
- `ion_pair_hydration_md/`：CAT/ANI 历史案例、坐标、拓扑和参数来源；新示例通过 catalog 副本解析。
- `docs/`、`skills/`：方案、审查约束与项目内操作指南。
- 根目录旧 `confout.gro`、其编号备份、`mdout.mdp`、`state.cpt`、`state_prev.cpt`、`timer.dat`：保留的历史输出，不是当前新 Run 输入；未经单独授权不删除或覆盖。
- `tmp/`：仅按需使用的中间文件位置；目录名不证明内容可重建，清理前检查实际文件，不能把其中资料默认当作有备份。

## Boundaries for New Material Systems

下列实验训练数据要求针对建立或验证新配方预测模型；不禁止明确标为研究假设、采用已说明模型与边界的 MD 探索。模拟不能替代所要求的实验标签。

- Do not use the Nature six-monomer model directly to predict DEM, DMM, DBM, NVP, VIm, AA, NIPAM, or any monomer absent from its training set.
- Protein-sequence statistics may define an initial formulation space or prior, but they are not experimental labels for synthetic gels.
- A new monomer system requires its own experimental training data. At minimum, record measured polymer composition, crosslinker level, total monomer concentration, thickness, pore architecture, pH, ionic strength, and temperature protocol.
- For thermoresponsive gels, distinguish the LCST or cloud point of a polymer solution from the volume phase transition temperature (VPTT) of a crosslinked gel. Prefer the definition that matches the actual measurement.
- For LCST smart-window materials, record more than the transition temperature: also record transition width, heating/cooling hysteresis, `t90`, low- and high-temperature transmittance, cycle stability, and sample thickness.
- Interpret charged comonomers together with pH and ionic strength. Do not describe VIm as permanently cationic, and do not assume AA is fully ionized under every condition.
- Use distinct language and fields for model predictions, chemical-mechanism inferences, and experimental validation. Never substitute one for another.

## 环境与命令

- 仅维护原生 macOS/Linux 路线。项目编排使用 Python；必要的调度脚本使用 POSIX shell。不新增 PowerShell、Windows 路径、WSL 或 Windows 兼容分支。
- 按平台分别建立环境，禁止跨系统复制虚拟环境或二进制；不从量化项目继承依赖和机器路径。先复用已验证的本地环境，不自动安装软件。
- 当前复用 `zwitterion_hydration_md/.venv-macos-analysis/`，实际解释器与依赖以模块 README 和本机检查为准；版本变更先做兼容性评估，不修改全局 Python 环境。
- 使用当前模块 README、实际参数解析器和测试配置中的真实命令，不把方案示例作为现成入口。工具缺失或 README 与源码矛盾时明确报告，不偷偷换引擎、参数或解释器。
- 命令中显式确定解释器、工作目录、输入和输出位置；路径支持空格与非 ASCII 字符。输出不得落入原始数据目录。
- 依赖变更须同步所属模块的环境说明与可复现记录；种子或特征顺序的授权变更也须记录。环境目录、wheel、缓存和临时渲染不属于源码。

## Implementation Conventions

- Use UTF-8, `pathlib.Path`, explicit function entry points, and serializable run metadata in Python code.
- Put units in column names or axis labels, such as `_kPa`, `_C`, or `_s`. Never rely on surrounding context to imply units.
- 不得通过比例归一化悄悄改变 MD 的显式组分计数、净电荷或组成约束；保存足够精度，显示舍入不改写科学输入。
- Keep data cleaning, feature construction, training, and candidate selection as separately inspectable steps.
- For small materials datasets, report cross-validation distributions, holdout error, and uncertainty where available. Do not report only training-set goodness of fit.
- Do not improve apparent performance by deleting inconvenient samples, selectively reporting random seeds, or showing only the best run.
- Compare every new model with a simple baseline. Do not add dependencies or complexity without demonstrated value.

## 工程维护规则

- 先搜索已有能力、相邻测试和调用方；只修改任务相关内容，不顺带重构或批量补注释。
- 正确性与科学可追溯优先，其次是清晰、单一职责和可维护性。避免提前创建插件框架、通用工厂、空实现或未来兼容层。
- 新增或实质修改的函数/类须有说明用途、关键参数和返回值/职责的 docstring；不直观的单位、坐标与算法假设须注释。
- 源码文件以约 400 行、函数以约 80 行为拆分提醒，不机械裁剪；文档不受此行数目标约束。
- 在用户输入、文件、外部工具和模块交接边界检查约定；缺失参数、无效数值和身份不一致应明确失败，不能靠吞异常、补零或换默认值伪造成功。
- Git 写操作须经授权；不清除用户改动，不绕过钩子，不提交凭据。发现敏感信息时不回显内容，先报告其位置与风险。

## 文档与证据归属

- `docs/plans/` 是工作区方案的唯一规范目录；不另建第二套工作计划树。新方案用日期和主题命名，至少记录状态、创建/更新时间、范围及是否实施。
- 探索假设与稳定知识分开维护：未来需要时分别使用 `docs/ideas/`、`docs/knowledge/`；当前没有内容则不创建空目录。
- README 说明实际入口；AGENTS 规定边界；Skill 指导操作；方案说明未实施设计；正式结论必须链接原始来源或具体运行证据。
- 文档迁移保留来源与替代关系，不制造两个可独立修改的规范副本。已有索引在新增/迁移文档时同步；普通运行不改知识库、索引或研究笔记。
- 本地运行使用明确存储位置，不硬编码某个外置盘。新模拟 Run 的轨迹、日志、检查点不放源码中；历史输出暂留原处，不因新规则自动搬移或删除。

## Verification Requirements

Choose the smallest verification that is sufficient for the risk of the change:

- Documentation-only changes: verify paths, commands, field names, and units.
- 模拟修改：按模拟局部规则选择单元测试、真实小量贯通或科学验证；报告 macOS/Linux 各自是否实测。
- 不通过删断言、跳过失败用例、伪造输入或提高容错来使测试通过。普通代码改动至少执行一次相关测试；环境不足时说明未跑项目与原因，不声称验收完成。
- Presentation, chart, or spreadsheet deliverables: inspect every page or sheet and verify that there are no clipped elements, unresolved placeholders, incorrect units, or untraceable numbers.

At handoff, state what changed, which checks ran, which checks did not run and why, and any known limitations.

## Data and File Protection

### Always

- Treat the authors' original data, original scripts, and user-provided papers or SI as read-only sources.
- Write new results to an explicit output directory and preserve run configuration, dependency versions, random seeds, and timing information.
- External PDFs, spreadsheets, and videos may be copied into `tmp/` for processing, but the originals must not be modified.
- Support scientific claims with the paper, SI, public databases, or traceable project data whenever possible.

### Ask First

- Change the research objective, feature definitions, experimental labels, or formulation space.
- Download new data, install dependencies, or access authenticated or paid resources.
- Overwrite a formal output, move original data, or start a long-running large-scale search.
- Present exploratory results as publication-level conclusions, experimental facts, or externally distributed material.

### Never

- Modify retained original scientific inputs or reference scripts to make an implementation appear correct.
- Write model predictions into experimental-measurement columns.
- Fabricate experimental results, citations, sample sizes, units, error bars, or model performance.
- Claim that the original Nature model validates new monomers or LCST gels without new experimental labels.
- Delete user files, reset the environment, or change the global Python configuration to repair this project.

数据保护中的禁止删除指未经明确授权的清理；授权删除仍须核对具体目标、备份/可恢复性并单独报告。迁移成功或有哈希记录不自动授予删除权限。

## Maintaining This File

- Add only project rules that prevent a real, recurring error. Do not collect generic programming slogans.
- If a new directory develops an independent workflow, prefer a shorter and more specific `AGENTS.md` in that directory. The instruction file closest to the target files governs the subproject.
- Update this file when commands, directories, or scientific definitions change, and remove obsolete rules.
- Keep this file quick to scan. Detailed experimental plans, paper notes, and one-time task state belong in the relevant README or deliverable.
