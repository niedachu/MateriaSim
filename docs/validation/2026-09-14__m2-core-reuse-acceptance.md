# M2：ZIL / CAT / ANI 共用核心工程验收

- 日期：2026-09-14；阶段状态：M2 当前范围通过 macOS CPU 工程验收。
- 科学状态：`not_assessed`；Linux/GPU、平衡、物性与统计收敛未验收。
- 对应[实施方案](../plans/2026-09-14__multicomponent-multiscenario__implementation-plan.md) M2、T1/T2，另重复受限恢复负例。
- M3 自动按数量装配、混合溶剂、无水周期回归和非水化分析未实施。本机未找到 Packmol，尚待安装授权；具体混合溶剂未选定。

## 实际改动

`config_v2.py` 支持多个独立模型与精确覆盖的 `model_hashes` 模型包；`prebuilt.py` 检查固定混合结构的计数、原子顺序、盒子和完整分子拓扑；`gromacs_build.py` 冻结模型/公共参数/结构，并接入同一 build/run/resume/analyze 核心。运行器没有按 ZIL/CAT/ANI 名称分支，没有复制离子对 runner。

新增 `cat_model.json`、`ani_model.json`、`cat_ani_bundle.json`、`cat_ani_protocol.json`、`cat_ani_smoke.json`。固定结构位于 scenario，模型本身不携带实验计数或 MDP。原 ZIL 示例与单模型 bundle 保留为真实调用，不维护第二套执行器。

新增 8 项 `test_prebuilt.py` 测试；通用化 `check_resume_guards.py`；新增真实证据审计 `verify_m2_evidence.py` 和单帧迁移比较 `compare_pair_single_point.py`。后两者是显式运行的验收工具，不属于单元测试自动发现，不启动长 MD。

没有安装软件、运行 PowerShell、修改 ML 环境、原始参数/MDP、旧 runner 或正式结果。旧数据未迁移或删除。

## 模型来源及限制

- CAT 独立 33 原子，序列化电荷 +0.999999 e；ANI 独立 8 原子，电荷 -1 e；总计约 -0.000001 e。没有为凑整数电荷重新拟合或修正。
- 坐标与 ITP 分别核对原 `parameterization/results/cat`、`ani` 元数据的输出哈希。既有 `topology/gaff2_atomtypes.itp` 的 11 项等于两套独立类型表的精确去重并集，共有项无冲突，使用的原子类型全部覆盖。
- CAT 两项原 GAFF 默认 improper 警示 `c3-cc-na-cd`、`c3-cc-na-cc` 保留；工程跑通不增加其科学适用范围。
- 模型包固定当前 GROMACS 2026.3 的 `amber14sb.ff`、TIP3P 与辅助库。有效 defaults 为 `1 2 yes 0.5 0.83333333333333333`；哈希为 `c073cc4a461823a4cfdf0413b6a20f5b631c0122c5575c543fcf04fd0ab48503`。
- 旧案例 README 的进度说明与现存后期报告不一致。原文件保留，不能仅据 README 推断旧项目没有正式计算。
- 本机没有找到原 Windows Run 的完整含水坐标/轨迹及完整安装库快照。因此本验收不声称重现旧 Windows 数值、历史水分子位置或正式水化结论。

本次沿用原 41 原子的 `smoke/input/pair_initial.gro` 与 4.5 nm 立方盒，不平移/重建溶质；在 Mac 原生 GROMACS 新建水盒并要求 SOL 恰为 2957。`gmx solvate -maxsol` 是计数上限，可能留下空隙，程序另检查实际数量；它不是平衡或密度验证。[GROMACS solvate 文档](https://manual.gromacs.org/current/onlinehelp/gmx-solvate.html)

## 预算与环境

- macOS 原生 CPU，Python 3.9.25、GROMACS 2026.3-Homebrew、MDAnalysis 2.7.0、NumPy 1.26.4。
- GROMACS 二进制 SHA-256：`fb47dc305b11b8a3189ae30f7402776f732e71734e6d778894528a1914f8df0e`。
- 每次模拟 2 CPU 线程、执行预算 60 秒；检查点测试使用 2 秒预算。编译和邻居表退出宽限不属于硬秒级截止。
- 每个案例 EM 上限 5000 步，NVT 1000、NPT 1000、采样 2000 步，dt 0.002 ps，共 8 ps MD；未运行原正式长协议。
- CAT/ANI 保留原 NVT seed 192837，温压/非键/约束等取其冻结 MDP；工程步数、输出频率与时间原点派生保存在 Run 的 `build/protocol_overrides.json`。ZIL 示例不改。
- 额外两次同帧 rerun，每次最多 60 秒，不积分长轨迹。

## 实测结果

| 检查 | 结果 |
|---|---|
| 单元测试 | 45 项通过，包括 8 项新增模型覆盖/计数/顺序/连接负例 |
| ZIL 回归 | 8910 原子，ZIL 1＋SOL 2957；EM 1072 步达到 Fmax < 500；NVT/NPT 各 1000 步，采样 2000 步 |
| CAT/ANI | 8912 原子，CAT 1＋ANI 1＋SOL 2957；EM 952 步达到 Fmax < 500；NVT/NPT 各 1000 步，采样 2000 步 |
| 真实恢复 | CAT/ANI NVT 预算中断于 640 步、1.28 ps，原检查点 append 后达到 1000 步、2 ps，再完成后续阶段 |
| 隔离负例 | 改 CAT 输入、检查点、轨迹均拒绝；中断态重新 run 也拒绝。被拒绝修改不产生新执行 attempt |
| ZIL 科学输入 | 与 M1 基线的 37 个冻结输入/构建文件一致，四阶段展开拓扑相同；每阶段 184 项有效参数物理一致 |
| 新旧分析 | 两个案例分别在同一新轨迹上比较，均 21 帧、各位点及水并集计数完全一致 |
| 原资产保护 | 88 个指定旧 CAT/ANI 参数、输入和报告文件哈希保持不变；不表示审计了整台电脑 |

ZIL 的 EM/NPT/采样阶段 `gen-vel=no` 时，grompp 自动解析但未使用的 `gen-seed` 数字不同，已逐项记录；活跃 NVT 速度种子不变。没有忽略有效物理参数差异。

## 单帧能量与力迁移对照

参考路径独立复制原 `formal/input/system.top`、CAT/ANI/公共 ITP；新路径读取框架构建拓扑。两者均使用相同的新 Mac EM 末帧、当前冻结力场库及 NVT 有效参数，仅统一派生 `nsteps=0` 与单帧力/能量输出。用原生 `grompp` 各自编译，再用 `mdrun -rerun` 计算固定帧；不把它称为旧 Windows 复现。[GROMACS mdrun 文档](https://manual.gromacs.org/current/onlinehelp/gmx-mdrun.html)

比较前记录阈值：势能绝对差 ≤ 0.001 kJ/mol；力分量 RMS 差 ≤ 0.001、最大差 ≤ 0.01 kJ/(mol·nm)。这些仅是同引擎同输入迁移用阈值，不是通用材料验证标准。TRR 禁用单位转换，使用原生力单位。

- 两边势能均为 -152396.546875 kJ/mol，输出精度下差为 0。
- 8912 原子的力分量 RMS 差为 3.450973357286872e-05，最大差 0.00018310546875 kJ/(mol·nm)，通过预设阈值；没有声称逐位一致。
- 184 项有效 MDP 参数一致，展开拓扑数据一致。源 Run 全文件哈希前后相同。
- 审计脚本首次把 defaults 电荷缩放系数误写为截短的 0.8333，断言失败；核对冻结 forcefield.itp 与原生 processed.top 后修正为真实精度并重跑通过。未改模型或放宽容差。

## 明确证据位置

工程证据根：`/private/tmp/materials-m2.hyZ5Dn`。这是可被系统清理的临时验收目录，不是长期科研归档；下列身份固定，不使用 latest/best。

- [整体审计](</private/tmp/materials-m2.hyZ5Dn/acceptance.json>)。
- [CAT/ANI Run](</private/tmp/materials-m2.hyZ5Dn/工程 验收/cat_ani_smoke-f9dc450f16a94bcf8ba2b5f545feac70/manifest.json>)。
- [ZIL Run](</private/tmp/materials-m2.hyZ5Dn/工程 验收/zil_smoke_v2-c632ce821cd6430fb8ad86ea8d60067c/manifest.json>)。
- [单帧比较与哈希](</private/tmp/materials-m2.hyZ5Dn/single-point/comparison.json>)；同目录 definition.json 在计算前保存输入与阈值。
- [恢复保护结果](</private/tmp/materials-m2.hyZ5Dn/guard-fixtures/guard_results.json>)。
- [CAT/ANI 21 帧比较](</private/tmp/materials-m2.hyZ5Dn/pair-analysis-comparison/comparison.json>)与 [ZIL 21 帧比较](</private/tmp/materials-m2.hyZ5Dn/zil-analysis-comparison/comparison.json>)。
- 原资产保护清单 `ion_pair_hashes.json`；完整实现身份、源参数、实际命令和阶段证据分别在对应 Run 内。
- 原核心备份 `baseline/`；未删除备份、负例副本或任何失败证据。

## 交付边界

M2 是两套具体案例共用可运行核心，**不是任意组分数量自动构建**。修改 count 与固定结构不一致时必须报错。水以外的溶剂、无水场景、组分接触分析、聚合物/固相/界面均不能从本轮结果推导为已实现。

下一步按 M3 先落实 Packmol 原生安装许可，在既有 ZIL/CAT/ANI 模型范围内做真实多副本/多组分装填及全局参数核查；混合溶剂须另选具体化学与参数。M3 缺任一必需项时只发布已完成子集，不标整阶段完成。

迁移说明（2026-09-15）：本记录从 `materials_simulation/docs/2026-09-14__m2-core-reuse-acceptance.md` 移至 `docs/validation/`。正文的运行命令、包名、阶段完成范围与绝对证据路径是当时的历史事实；当前入口以根 README 为准。只修正相对文档链接，不改写 Run。
