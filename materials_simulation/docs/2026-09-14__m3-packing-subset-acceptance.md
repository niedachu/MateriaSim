# M3：已有模型自动装配子集的 Mac CPU 工程验收

日期：2026-09-14。状态：**当前子集通过；M3 整体未完成，科学质量未评估**。

本记录对应[实施方案](../../docs/plans/2026-09-14__multicomponent-multiscenario__implementation-plan.md)修订 5。它新增本轮事实，不改写 [M1](2026-09-14__m1-core-acceptance.md) 或 [M2](2026-09-14__m2-core-reuse-acceptance.md) 的历史记录。

## 交付和模型边界

已从“读入一套预建混合结构”推进到从单分子模板自动生成副本：ZIL、CAT、ANI 按正整数数量装配，支持同模型多个初始区域，选择 TIP3P 填水或无水正交周期盒，共用已有 GROMACS 阶段/续跑核心。增加独立组分接触分析与只读 `capabilities` 查询；实际命令见 [README](../README.md)。

新职责为 `assembly.py`（数量/参数校验与派生拓扑）、`packmol.py`（原生装填与几何校验）、`gromacs_packed.py`（装填产物交接）和 `component_contacts.py`（周期唯一分子对计数），均在 `materials_sim/`。没有创建第二套 runner 或空后端。

- 原 ZIL/CAT/ANI 模型、原 MDP、原 runner、历史 Run 不变，没有重新参数化。原 CAT/ANI 资产清单 88 个文件哈希通过；ZIL 来源文件按模型/协议哈希验证。
- ZIL 的原分子 ITP 内嵌公共类型，CAT/ANI 的类型来自独立公共表；合并时逐 token 比较相同名称的类型，11 个类型一致。只有派生 `build/` 拆出公共表和分子 ITP；原始文件完整冻结，记录转换哈希。
- 目前只接受已有显式 GAFF 形式和有限分子图，要求类型/质量/电荷/键合项完整、连通及数量匹配。全局 defaults/缩放约定固定核查，展开拓扑再次核对原分子参数。没有自动补项、混搭力场或提高 `maxwarn`。
- bundle 是 `engineering_only`。继承 M2 的 CAT 参数来源及 improper 适用性限制，不因能装填而新增物性或跨材料验证结论。
- 水仍是 bundle 覆盖的 `tip3p_fill` 策略，尚非可与任意溶剂共同按整数数量装配的独立模板；记录的是实际分子数分数，不是指定浓度或体积分数。
- 初始区域不是动力学限制；无水周期盒不是非周期真空、固体、聚合物熔体或凝聚态密度验证。

## 环境与安装

用户继续授权范围是安装原生 Packmol、推进已有模型自动装配并做小量验收，没有选择新的混合溶剂/聚合物/晶体。

本机 macOS CPU：Python 3.9.25、GROMACS 2026.3-Homebrew、MDAnalysis 2.7.0、NumPy 1.26.4；复用 `zwitterion_hydration_md/.venv-macos-analysis`，未改 ML 环境或全局 Python。

本轮新装 Packmol 21.2.3 原生 arm64 bottle；使用 Homebrew 的禁止自动更新、禁止清理及禁止升级已安装依赖选项。安装后本机 GCC 仍为 16.2.0、xz 仍为 5.8.3；下载的缓存不等于已安装版本。没有信任额外 tap，没有 PowerShell、Windows/WSL 路线，也未安装 Polyply、ASE、LAMMPS 或新 Python 包。

| 工具 | 本机位置 | SHA-256 |
|---|---|---|
| Packmol 21.2.3 | `/opt/homebrew/Cellar/packmol/21.2.3/bin/packmol` | `dd1fb66aff8e9fca0cda2580cd8f8617d15845250b4538c57836da60ba7cd748` |
| GROMACS 2026.3 | `/opt/homebrew/Cellar/gromacs/2026.3_1/bin/gmx` | `fb47dc305b11b8a3189ae30f7402776f732e71734e6d778894528a1914f8df0e` |

Packmol 采用 ≥21.1.0 的 `-i` 文件接口，不使用不可回读的 stdin 管道；正交周期装箱及输入字段依据 [Packmol 官方手册](https://m3g.github.io/packmol/userguide.shtml)。安装来源见 [Homebrew Packmol](https://formulae.brew.sh/formula/packmol)。Linux 需自己建立原生环境、核对冻结库并验收，不复制 Mac 二进制。

## 固定工程预算与协议

- 四例盒长均为 4.5 nm，Packmol 种子 73129、分子间距离目标 0.25 nm、nloop 100、优化精度 1e-6；每次构建只有一次有限尝试、装填超时 60 秒，不自动扩盒/改种子/减数量。
- 输出检查采用 GRO 0.001 nm 精度，几何/区域偏差上限 0.002 nm，并独立核查 PBC 分子间距离和模板内部距离。上限为 2,000 个非溶剂原子、20,000 个总原子，净电荷仅容许 0.001 e 内已有参数舍入残差。
- 水例使用已有短程协议：EM 上限 5,000 步、Fmax <500；NVT 1,000、NPT 1,000、prod 2,000 步，dt 0.002 ps，共 8 ps MD。温压、电荷、力场、水模型、约束沿用原模板，工程派生保存在 Run 中。
- 无水例为 EM＋NVT 1,000 步（2 ps），无压强耦合；新增 [dry_em.mdp](../examples/dry_em.mdp) 仅删除原 EM 中无水时无用途的 `-DFLEXIBLE` 宏，未改原文件。该派生文件哈希为 `435b9dc34c84376519bd308f9832b3e38e9f094d07ca6a14cd374b22a7ea6622`。
- 实际采用 2 CPU 线程、单次执行 60 秒预算；三组分 NVT 另以 2 秒预算验证中断。邻居搜索停机边界、构建/编译和退出宽限不等于严格墙钟硬截止。没有正式长采样。

## 最终四个真实 Run

共同根目录为 `/private/tmp/materials-m3.wGyi1a/最终版本/`。以下均为最终当前源码身份，并非较早开发版本的结果。

| 示例 / Run 目录名 | 实际组分数 | 原子数 | 完成情况 |
|---|---|---:|---|
| `packed_zil_water-e70e9ddc9f7f46a89815a5dd307a4918` | ZIL 2，SOL 2941 | 8901 | EM 1053 步达力阈值，8 ps MD |
| `packed_ions_water-977e24be58ef4e01b3214edc5d352a94` | CAT 2，ANI 2，SOL 2941 | 8905 | EM 923 步达力阈值，8 ps MD |
| `packed_mixture_water-4c64da6138744aa8a88e8e7f879809a0` | ZIL 1，CAT 1，ANI 1，SOL 2939 | 8897 | EM 1077 步达力阈值，8 ps MD |
| `packed_zil_dry-efbbf526f934473c89bc014abc7e3a63` | ZIL 2，无 SOL | 78 | EM 18 步达力阈值，2 ps NVT |

逐阶段完成依据为力标准、检查点实际步数/时间及日志，不仅是退出码。三组分 NVT 在 640/1000 步、1.28 ps 实际中断，原检查点 append 恢复至目标，再完成后续阶段。隔离副本分别修改输入 ITP、CPT、XTC 均被拒绝，向 interrupted Run 重新 run 也被拒绝；原 Run 未修改。

ZIL 水例 left/right 两组各一个副本，实例组计数、分子身份与原子 UID 唯一性检查通过。四例装填后的 PBC 最小分子间原子距离分别为 0.703456、0.434723、1.065106、0.457973 nm，均满足该固定距离目标及序列化精度。

## 测试与分析证据

从模块目录使用已有解释器运行 `python -B -m unittest discover -s tests -v`：**66 项通过**（原 45 项＋新增 21 项）。负例覆盖数量/区域/实例组冲突、保留 ID、类型冲突、缺项/宏、带电组合、无水压强/水化请求、缺工具/低版本、PBC 重叠和单位/原子顺序；接触测试覆盖多原子去重、同组分排除自身和周期情况。

`tests/verify_m3_evidence.py` 审计四个完成 Run 的源码身份、冻结文件、实际组成、实例映射和原资产，并在外部目录创建独立 AnalysisRun。参考算法使用轨迹副本与独立最小镜像双循环，不复用生产 `capped_distance` 计数路径。

三个水例各 21 帧、无水例 11 帧，逐帧时间和唯一分子对计数完全一致；分析前后原 Run 全部文件哈希不变。0.5 nm 阈值下水例计数均为 0，无水例均为 1；这只是短轨迹算法验证，不是“水中没有接触”或“干态存在结合”的科研结论。无平衡剔除、自相关校正、独立重复或置信区间。

同一 Packmol/GROMACS 环境、同物理输入与种子的较早构建和最终构建比较：四例 `packing.inp`、`packed.pdb`、`boxed.gro`、`solvated.gro` 全部哈希相同。仅证明本机这四组初始化重建，不承诺跨平台/版本或 MD 轨迹逐位一致，也不把重复构建算作独立科学重复。

本轮工程证据根为 `/private/tmp/materials-m3.wGyi1a/`：

- `final-unit-tests.log`：66 项测试日志。
- `evidence/acceptance.json`：最终源码哈希、四例逐阶段事实、工具身份、分析/参考路径。
- `evidence/analysis/`、`evidence/reference/`：独立分析与逐帧算法对照。
- `checkpoint_stop.json`、`final-resume-guards/guard_results.json`：真实中断及隔离负例。
- `regression_diagnosis.json`：旧入口差异与四例固定种子重建比较。
- `baseline/`：改动前核心；`published/`：发布快照。均为工程辅助，不是第二个维护入口。

这些路径是临时工程证据，可能被系统清理，**不是长期科研归档**；本轮没有获得归档搬迁/删除授权。代码、配置和本验收摘要在项目中保留。

## 开发中失败与修复记录

失败现场均保留在同一工程根的 `工程 验收/`，没有删日志、改 Run 状态或覆盖旧 attempt：

1. 三组分初次 `b732a94d017441fc884bdcec25d928ce`：Packmol 的 Fortran 回读 stdin 管道报 Illegal seek。改为原生 `-i` 文件接口并检查版本下限后，新建 Run 通过。
2. 离子副本 `c1b590e7c6b04d0f923e11d1128162a7`：默认 Packmol 精度使原子 y 达 4.5047 nm，超出 4.5 nm 区域及 0.002 nm 允许误差。提高优化精度至 1e-6，保持种子/数量/盒/距离和验证误差不变，重建通过。
3. 无水 `a91dc6ef32c84e3297169aa4c6470483`：grompp 拒绝未使用的 FLEXIBLE 宏。仅在新增无水 EM 模板删除该宏，未使用 `-maxwarn`，新建 Run 通过。

另保留较早 ready/interrupted/completed 开发 Run。后续仅在最终源码冻结后重新跑四例作为交付证据，不将较早源码的成功冒充当前验证；不跨源码恢复旧中断 Run。

## 旧入口回归的已知限制

附加的严格字节回归 `check_regressions.py` 对旧 ZIL 通过，但对旧 CAT/ANI 的 `build/solvated.gro` **失败**，该失败未删除或改成通过。另行只读差异审计确认：冻结 inputs、干态坐标、拓扑、原子映射、展开 EM 拓扑及有效物理参数相同；EM 的非激活 gen-seed 差异单独记录。两份水盒均 2957 个水、8912 原子，但各有一个对方没有的水分子坐标。

两次同参数 solvate 均先得到 2958 个水，再按旧 `-maxsol 2957` 去掉一个。[GROMACS v2026.3 源码](https://raw.githubusercontent.com/gromacs/gromacs/v2026.3/src/gromacs/gmxpreprocess/solvate.cpp)中 `removeExtraSolventMolecules` 使用运行时随机种子选择删除对象，解释了该差异；命令帮助的“只取前若干个”描述不能用来保证本版本逐字节重建。

因此：旧入口能构建、计数和参数保持，但“重新加水精确恢复旧初态”未通过，也未在本轮改变其旧构建语义。精确读取/分析应使用已冻结 Run；历史 Run 完整性验证正常。未来若要保证固定水数的确定性重新构建，需单列有版本的构建策略与验收。新 packed 填水路线不使用 `-maxsol`，本轮四例重建比较通过。

## 下一步与未验收项

M3a 仍缺选定混合溶剂及完整模型、水/其他溶剂显式按数量共装；M3b 的摩尔/质量配比与浓度解析未实现。需要用户确定实际溶剂组合后核查模型来源、兼容与预算，不从示例自动选择材料。

聚合物单链/溶液/熔体属于 M4，晶体/LAMMPS 属于 M5，纳米材料/界面/复杂复合属于 M6，均未实施。Linux/GPU、平衡、材料物性、跨材料科学有效性和灾难恢复未验收。按 simulation-research 与 simulation-diagnostics 技能，工程成功、失败诊断和科学证据分别记录，不以数值跑通替代后续科学验证。
