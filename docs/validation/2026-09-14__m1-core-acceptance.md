# M1 核心重构：macOS CPU 工程验收

日期：2026-09-14。状态：M1 当前 ZIL 子集通过；M2—M6 未实施。科学质量：未评估。

本记录对应用户授权“开始做”的第一阶段，不把本次核心重构称为多组分/聚合物/固相能力已经实现。原 [第一轮记录](2026-09-14__mac-framework-acceptance.md)及其 Run 不改写。

## 改动与范围

- 新建 v2 模型、相互作用包与协议示例；模型不再携带 MDP 或实验数量。新运行仅 v2，实际仍只支持一个预建组分的 TIP3P 水盒。
- 线性阶段 ID 与类型分离；允许重复 dynamics，显式指定前驱、坐标/检查点输入、速度方式、种子、时间/步数原点。GROMACS 编译/执行/评估移出通用编排。
- 原子映射和已构建体系有独立记录；阶段封存输出带角色、格式、哈希、单位和实际步数/时间。
- 历史完整性读取与执行权限分开，递归记录当前源码身份。v1 可以只读查询/重分析，不用新代码原地执行；v2 续跑仍要求原代码、引擎、输入/TPR/输出身份一致。
- 分析可关闭、可选非 prod 中间阶段；每次分析生成外部 AnalysisRun，包括输入副本、请求与来源、实现、报告和独立状态。MDAnalysis 缓存只写副本旁。

源码责任与真实命令见 [README](../../README.md)。方案进度见 [实施方案](../plans/2026-09-14__multicomponent-multiscenario__implementation-plan.md)。

未安装依赖，未调用 PowerShell/WSL，未修改全局/ML 环境，未改旧 ZIL/CAT/ANI 参数或原始 MDP，未清理用户文件。当前工作区未建立 Git 仓库；没有执行 Git 写操作。

## 环境、预算与基线

复用本机原生 Python 3.9.25、GROMACS 2026.3-Homebrew、MDAnalysis 2.7.0、NumPy 1.26.4，2 CPU 线程；版本与真实测试输出保存在 [final_checks.json](</private/tmp/materials-m1.cNL9wj/final_checks.json>)。

授权小量批次上限为 4 个新计算 Run，本轮实际 2 个。每个为 8,910 原子：1 ZIL＋2,957 SOL，4.5 nm 立方盒，dt=0.002 ps，每个总 MD 8 ps。EM 上限 5,000 步，MD 阶段不超过 2,000 步；使用 60 秒执行预算，以及一次刻意的 2 秒预算中断，不运行生产协议。变更保护另建一次性副本，不运行新 MD。

源码、测试、配置在改动前已复制并哈希：

- [v1 基线副本](</private/tmp/materials-m1.cNL9wj/baseline>)、[基线哈希](</private/tmp/materials-m1.cNL9wj/baseline_hashes.json>)。
- [历史 Run 初始全文件哈希](</private/tmp/materials-m1.cNL9wj/historical_hashes.json>)。

这些位置都是 `/private/tmp` 的临时工程证据，可能被系统清理，**不是长期科研归档**。没有移动、删除或替换旧 Run；永久存储和版本管理需另行确定。

## 实测结果

主证据：[acceptance.json](</private/tmp/materials-m1.cNL9wj/final-evidence-v2/acceptance.json>)。

| 检查 | 结果 |
|---|---|
| 修改前回归 | 原 22 项 unittest 通过 |
| 修改后回归 | 37 项 unittest 通过，无跳过失败用例 |
| ZIL 构建输入 | 37 项原输入/力场库/构建坐标/映射/最终拓扑哈希与历史一致 |
| 原生有效 MDP | 每阶段 184 个参数比较；生效物理参数一致，未启用的 gen-seed 差异单独记录 |
| 相互作用拓扑 | 四阶段 grompp 展开拓扑分别与历史同阶段哈希一致 |
| 原目标恢复 | NVT 在 640/1000 步、1.28 ps 中断，随后 append 到 1000 步，再完成 NPT/采样 |
| 变更保护 | 修改输入、检查点、轨迹的三个隔离副本均被拒绝，且未创建新执行 attempt |
| 防止误重启 | 对 interrupted Run 使用 run 而非 resume，被拒绝 |
| 历史新分析 | 旧轨迹 21 帧的各位点与并集计数逐帧完全一致 |
| 历史只读 | 原 Run 149 个文件的字节哈希与文件清单全部不变 |
| 新轨迹算法对照 | 新 v2 轨迹的 21 帧与旧 hydration_count 算法逐帧一致 |
| 非 prod 分析 | 五阶段案例的中间 sample 阶段产生 11 帧，约 14.2—16.2 ps |
| 空分析列表 | 返回空列表，不创建分析目录、不隐式执行水化 |
| 分析失败隔离 | 故意空水氧选择产生独立 failed AnalysisRun；源 MD Run 全部文件保持不变 |

### 基线 Run

[zil_smoke_v2-7fef51dcff454f03afa037c6d0c47059](</private/tmp/materials-m1.cNL9wj/工程 验收/zil_smoke_v2-7fef51dcff454f03afa037c6d0c47059>)：

- EM 861 步达到 Fmax < 500；NVT 1000 步/2 ps，NPT 1000 步/2 ps，prod 2000 步/4 ps。时间原点保持旧协议逐段从 0 开始，不把重叠时间轴直接拼接。
- 第一次执行停在 EM 边界；随后 2 秒预算触发 NVT 检查点中断，再恢复到原目标。未改 TPR、步数或原配置。
- [中断 attempt 的输出副本](</private/tmp/materials-m1.cNL9wj/工程 验收/zil_smoke_v2-7fef51dcff454f03afa037c6d0c47059/attempts/resume-9f597ab94b234551bfcb1669d2734356/outputs-nvt>)保留中断时轨迹/检查点；最终 seal 不冒充中断代证据。
- [恢复保护结果](</private/tmp/materials-m1.cNL9wj/guard-fixtures/guard_results.json>)、[新轨迹新旧算法对照](</private/tmp/materials-m1.cNL9wj/new-legacy-comparison/comparison.json>)。

### 重复阶段与非零原点 Run

[renamed_no_analysis-568cccceb6db4473a213f4050c0a4148](</private/tmp/materials-m1.cNL9wj/工程 验收/renamed_no_analysis-568cccceb6db4473a213f4050c0a4148>)，输入为 [实验配置](</private/tmp/materials-m1.cNL9wj/renamed_spec.json>)和[协议](</private/tmp/materials-m1.cNL9wj/renamed_protocol.json>)。

这是有意变更阶段组织与时间标记的工程对照，不作为与基线相同轨迹的声明；仍复用原模型及 MDP 模板。

| ID | 类型与输入 | 实际终点 |
|---|---|---|
| relax | minimization，初始坐标 | 995 步达到 Fmax < 500 |
| warm | dynamics，坐标＋生成速度；tinit=10 ps，init-step=100 | 绝对步 1100，12.2 ps |
| density | dynamics，warm 检查点 | 步 1000，14.2 ps |
| sample | dynamics，density 检查点 | 步 1000，16.2 ps |
| sample_more | dynamics，sample 检查点；再次使用采样模板 | 步 1000，18.2 ps |

默认分析为空；完成后通过独立请求分析 sample 而非最终 sample_more。见 [中间阶段报告](</private/tmp/materials-m1.cNL9wj/final-evidence-v2/analyses/renamed_no_analysis-568cccceb6db4473a213f4050c0a4148--middle_stage--6ac0683fec994f679056c4e6dabcee98/report.json>)。XTC 时间为浮点编码，报告保留实际精度，不手动四舍五入改数据。

## 对照中发现和处理的问题

1. 首次直接运行测试辅助脚本未设置 PYTHONPATH，导入 materials_sim 失败，没有开始 MD 或创建保护副本。按实际包入口改用 `PYTHONPATH=.` 后执行成功，并在 README 明示。
2. 第一次有效参数逐字比较发现 EM/NPT/prod 的 gen-seed 不同。这些阶段均 `gen-vel=no`，GROMACS 为未启用的速度生成参数解析随机值；NVT 的生效种子 271828 完全一致。依据 [GROMACS 速度生成语义](https://manual.gromacs.org/documentation/current/user-guide/mdp-options.html#velocity-generation)，测试改为：仅在两侧均 gen-vel=no 时单独记录此差异，其他参数以及实际生成速度的种子仍严格比较。增加了拒绝生效种子/dt 改变的回归，不修改模拟输入，也没有为此重跑 MD。
3. 故意无效分析选择属于负例；其失败证据保留在独立分析目录，不修改源 Run 状态。没有数值失败被忽略或用 maxwarn 绕过。

“输入与有效物理设置一致”不等于新旧不同次 MD 轨迹逐字节相同；本轮只要求同一固定轨迹的新旧分析计数一致。EM 收敛步数的不同如实保留。

## 再检查与尚未完成

从 materials_simulation 目录，用本机既有解释器执行 `python -B -m unittest discover -s tests -v`。辅助工具 `tests/check_resume_guards.py`、`tests/compare_analysis.py`、`tests/verify_m1_evidence.py` 的输入与外部输出均显式传参，命令选项见 `--help`；再次验收必须选择新的输出目录，不覆盖本记录关联数据。

Linux、GPU、其他力场版本、自动多组分装配、CAT/ANI 共用核心、链/聚合物/固相/纳米界面、父 Run 派生和灾难恢复尚未完成。短轨迹没有证明平衡、物性或参数的科学适用性；无有效独立样本数/置信区间。

本轮依照 [simulation-research](../../skills/simulation-research/SKILL.md) 固定工程问题、输入与预算，依照 [simulation-diagnostics](../../skills/simulation-diagnostics/SKILL.md) 核查中断/差异证据；不把工程成功升级为科研结论。下一步为 M2 的既有 CAT/ANI 资产核查与同核心接入，之后 M3 才交付真实多组分装配。

迁移说明（2026-09-15）：本记录从 `materials_simulation/docs/2026-09-14__m1-core-acceptance.md` 移至 `docs/validation/`。正文的运行命令、包名、阶段完成范围与绝对证据路径是当时的历史事实；当前入口以根 README 为准。只修正相对文档链接，不改写 Run。
