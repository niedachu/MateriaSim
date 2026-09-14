# Materials Simulation：已有模型的自动装配子集已验收

当前是原生 macOS/Linux 路线的受限工程核心，**不是已经支持任意多组分、多材料、多场景的平台**。M1/M2 及 M3 的既有模型自动装配子集在 macOS CPU 通过工程验收；混合溶剂尚缺，M3 整体未完成，M4—M6 未实施，Linux/GPU 未实测。

已有能力：独立模型/相互作用包/场景/协议/分析请求 → 冻结输入 → 预建结构或 Packmol 自动装配 → 可命名线性阶段 → 严格续跑 → 独立分析。ZIL/CAT/ANI 可按整数数量装配并加水；无水正交周期盒可做固定体积短测。聚合物、固相、纳米材料、混合溶剂和 LAMMPS 尚未实现。

M3 经授权新装原生 Packmol 21.2.3，复用现有 Python/分析环境；没有调用 PowerShell、修改 ML 环境、原模型/MDP 或历史 Run。无水专用 EM 模板另存，仅去掉无用途的水宏。详见 [M3 子集验收](docs/2026-09-14__m3-packing-subset-acceptance.md)；[M2](docs/2026-09-14__m2-core-reuse-acceptance.md)、[M1](docs/2026-09-14__m1-core-acceptance.md)与[第一轮验收](docs/2026-09-14__mac-framework-acceptance.md)保留为历史记录。

## 代码责任

| 文件 | 当前职责 |
|---|---|
| `schema.py` | 严格字段校验、版本入口、真实 v1 配置的只读解析 |
| `config_v2.py` | v2 的模型、相互作用包、组分计数、场景和分析请求解析 |
| `prebuilt.py` | 固定混合结构的数量、原子顺序、模型连接与预处理后一致性；不执行自动装填 |
| `assembly.py` / `packmol.py` | 区域/计数与显式 GAFF 参数合并；Packmol 调用、模板几何/PBC 距离检查 |
| `gromacs_packed.py` | 自动装配与同一 GROMACS 核心的交接，可加水或无水；不复制 runner |
| `protocol.py` | 阶段 ID/类型、继承、步数/时间原点校验；独立 MDP 派生 |
| `build.py` / `execute.py` | Run 与线性协议编排，不解释 GROMACS 输出 |
| `gromacs_build.py` / `topology.py` | 当前水盒构建器、力场库冻结、实际组成/原子映射 |
| `gromacs_stage.py` / `gromacs.py` | GROMACS 编译、执行、完成检查与原生检查点 |
| `files.py` / `state.py` / `records.py` | 内容身份、单写者、版本化读取、执行兼容和产物引用 |
| `analysis.py` / `hydration.py` / `component_contacts.py` | 独立分析调度、水化接触和唯一分子对接触 |
| `cli.py` / `__main__.py` | `python -m materials_sim` 入口 |

这些文件均在 `materials_sim/` 下。只实现当前具体 GROMACS 适配器，没有空后端、插件工厂或第二套执行核心。

## 环境与最短用法

从本目录执行；本机复用 Python 3.9.25、GROMACS 2026.3-Homebrew、MDAnalysis 2.7.0、NumPy 1.26.4。核心仅用标准库；分析依赖后两者。不需要安装此包，其他工作目录需显式设置 `PYTHONPATH`。Linux 使用自己的本地环境，不能复制 Mac 虚拟环境/二进制。

```sh
SIM_PY='../zwitterion_hydration_md/.venv-macos-analysis/bin/python'
"$SIM_PY" -B -m materials_sim doctor
"$SIM_PY" -B -m materials_sim validate examples/zil_smoke_v2.json

# 临时工程证据，不是长期科研归档。
SIM_RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/materials-smoke.XXXXXX")"
SIM_RUN="$("$SIM_PY" -B -m materials_sim build examples/zil_smoke_v2.json \
  --run-root "$SIM_RUN_ROOT" | "$SIM_PY" -c 'import json,sys; print(json.load(sys.stdin)["run_dir"])')"

"$SIM_PY" -B -m materials_sim run "$SIM_RUN" --threads 2 --max-wall-seconds 180
"$SIM_PY" -B -m materials_sim status "$SIM_RUN"
```

状态为 `interrupted` 才用 `resume` 继续原目标，不重新 `run`：

```sh
"$SIM_PY" -B -m materials_sim resume "$SIM_RUN" --threads 2 --max-wall-seconds 180
```

状态为 `completed` 后，分析写到显式指定的 **Run 外部** 目录：

```sh
"$SIM_PY" -B -m materials_sim analyze "$SIM_RUN" --output-root "$SIM_RUN_ROOT/analyses"
"$SIM_PY" -B -m materials_sim report "$SIM_RUN" --analysis-root "$SIM_RUN_ROOT/analyses"
```

`doctor / capabilities / validate / status / report` 是只读查询，不生成 Run 或启动 MD。`validate` 检查配置/资产；`executable=true` 只表示已实现的子集，不代替实际工具、`grompp` 或科学验收。`build` 可调用 Packmol/editconf/solvate/grompp，但不积分动力学。

自动装配额外需要原生 Packmol ≥21.1.0，使用其可回读文件的 `-i` 接口。已验收版本为 21.2.3；没有自动安装或替代构建器。`doctor --packmol packmol` 查询版本/哈希，`capabilities` 列出真实能力及未实现项，`build --packmol /path/to/packmol` 可指定程序。已构建 Run 的续跑不重新装填，不依赖当前 Packmol 版本。

`--gmx` 可用于 doctor/build/run/resume。`--through` 接受当前配置中的阶段 ID；默认终点是列表最后一个阶段，不再固定为 prod。每次执行最多 8 CPU 线程，墙钟参数 1—600 秒；邻居搜索停止边界、编译和退出宽限会增加实际耗时，不是整个命令的硬截止。

## v2 当前可运行子集

ZIL 示例是 [zil_smoke_v2.json](examples/zil_smoke_v2.json)，引用：

- [zil_model_v2.json](examples/zil_model_v2.json)：ZIL 身份与预建坐标/拓扑/参数文件哈希；没有 MDP 或实验分子数量。
- [zil_bundle.json](examples/zil_bundle.json)：精确模型内容哈希、GROMACS 力场目录与库文件内容哈希、TIP3P、`engineering_only` 范围。此记录不是任意力场混搭的批准书。
- [zil_protocol.json](examples/zil_protocol.json)：原始 MDP 的来源/哈希和有序阶段；不修改源模板。

CAT/ANI 示例是 [cat_ani_smoke.json](examples/cat_ani_smoke.json)，引用独立的 [CAT 模型](examples/cat_model.json)、[ANI 模型](examples/ani_model.json)、[相互作用包](examples/cat_ani_bundle.json)与[协议](examples/cat_ani_protocol.json)。把上述 build/validate 命令的配置路径换成该示例即可使用同一入口。

该场景读取原案例的 41 原子干态 `pair_initial.gro`，保持溶质坐标与 4.5 nm 盒不变，加水后严格检查 CAT 1＋ANI 1＋SOL 2957。它是新 Mac 工程水盒，不是缺失的旧 Windows 含水坐标/轨迹复现。`solvent_count` 通过 `solvate -maxsol` 后检查实际计数；不是浓度换算或平衡密度承诺。

补查发现旧 CAT/ANI 入口重新加水不保证逐字节复现：本机 GROMACS 2026.3 在超出 `-maxsol` 时随机删水，两次构建各有一个不同的水分子，计数/溶质/拓扑不变。精确历史初态应读取冻结产物，不能重新加水替代。新 `packed_liquid` 填水不使用 `-maxsol`，四个固定种子重建坐标比较通过；这是本机实测，不是跨版本保证。详见 [诊断记录](docs/2026-09-14__m3-packing-subset-acceptance.md#旧入口回归的已知限制)。

模型/包/协议当前通过相对配置文件的本地路径引用，不是全局 ID 注册中心。解析后内嵌内容并冻结哈希，不把主机路径混入科学内容身份。升级方案中的聚合物/固相 JSON 仍是设计示例，不能直接执行。

当前限制：

- `components` 可声明 1—8 个不同模型、每种 1—100 个分子。预建场景仍必须提供全部实例坐标，不自动复制；`packed_liquid` 才从单分子模板生成副本。多模型 bundle 必须以 `model_hashes` 精确覆盖全部模型，`files` 保存公共类型；原 ZIL 单模型 bundle 保留为真实既有调用。
- 场景为 `prebuilt_solute_water`、`prebuilt_mixture_water` 与 `packed_liquid`；仅正交三维周期盒，3—6 nm/边，总原子不超过 20,000。预建水盒仍要求 SOL；自动装配显式选择加水或无水，不能据此推断固相或非周期真空支持。
- 协议为 2—8 个线性阶段：首个 `minimization`，之后可重复 `dynamics`；ID 唯一。EM 最多 5,000 步，MD 每阶段最多 2,000 步、dt ≤ 0.002 ps。当前仅 steep/md 积分器。
- 每阶段显式声明前驱、coordinates/checkpoint 输入、none/generate/inherit 速度方式、生成速度种子及时间/步数原点。首段 MD 生成速度，随后从前驱检查点继承；同阶段恢复始终使用原 TPR 的 `-cpi/-append`。
- `time_origin_ps` 对应 tinit，`step_origin` 对应 init-step。目标绝对步数为 step_origin＋steps，目标时间为 time_origin_ps＋dt×目标绝对步数。跨阶段重置时间必须显式配置；当前分析只处理单个完成阶段，不拼接时间可能重叠的轨迹。
- 基线仍是 4.5 nm、EM 5,000 上限、NVT/NPT 各 1,000、采样 2,000 步，共 8 ps MD；原力场、电荷、水模型、温压、约束及 dt 不更改。工程步数、输出频率、速度种子和明确时间原点的派生记录在 `build/protocol_overrides.json`。
- 安装态力场库不匹配 bundle 哈希时拒绝构建，不能自动修改哈希跳过检查。Linux/其他 GROMACS 版本需核对库身份并另做真实验收。

时间与速度语义依据 [GROMACS MDP 文档](https://manual.gromacs.org/documentation/current/user-guide/mdp-options.html)，阶段状态输入依据 [grompp](https://manual.gromacs.org/current/onlinehelp/gmx-grompp.html)。

## 自动装配：现有模型的可运行示例

以下配置可直接替换前述 build 命令的配置路径；每次创建新 Run，不改原始模型：

| 示例 | 实际能力 |
|---|---|
| [packed_zil_water.json](examples/packed_zil_water.json) | ZIL×2＋水，同一模型分别放入 left/right 两个初始区域 |
| [packed_ions_water.json](examples/packed_ions_water.json) | CAT×2＋ANI×2＋水，多副本及电中性检查 |
| [packed_mixture_water.json](examples/packed_mixture_water.json) | ZIL＋CAT＋ANI＋水，三种非溶剂共同装配 |
| [packed_zil_dry.json](examples/packed_zil_dry.json) | ZIL×2、无水周期盒，EM＋固定体积 NVT 短测；不代表固体/熔体 |

例如：`"$SIM_PY" -B -m materials_sim validate examples/packed_mixture_water.json`。

`scenario.groups` 的每组包含唯一 `id`、已声明 `component_id`、正整数 `count` 和三维 `min_nm/max_nm`。同一模型可以在多组出现，各组计数之和必须等于 components 中的总数。`solvent_fill` 是自动水组保留 ID。区域只约束初始装填，不是动力学约束或界面制备。

`seed` 为装填种子，独立于协议速度种子；`tolerance_nm` 为分子间目标原子距离，`max_iterations` 为有限 Packmol 优化循环数。仅一次固定种子尝试，最多 60 秒，不自动重试、减数量或扩盒。Packmol 精度固定为 1e-6；输出按 0.001 nm GRO 精度检查，几何/区域误差上限 0.002 nm，同时核对周期最小镜像距离。

`solvent.kind` 仅支持 `tip3p_fill` 或 `none`。前者用已冻结 TIP3P/水库填充剩余空间，记录实际水数和分子数分数，不保证指定浓度；后者不加水且当前要求固定体积协议、禁止水化任务。[dry_em.mdp](examples/dry_em.mdp) 来自原 ZIL EM，只去掉无水时无用途的 `-DFLEXIBLE`；原文件不变。

装配子集最多 2,000 个非溶剂原子，要求显式电中性（仅容许既有序列化舍入残差）、连通单分子、明确逐原子电荷质量及当前 GAFF 键合形式。用户分子文件中的宏/include、缺失类型、同名类型不同参数、隐式键合项均拒绝。公共类型去重及分子 ITP 派生只写 Run 的 `build/`，保留原文件与转换哈希，并用原生展开拓扑逐项核对。

`build/packing/` 保存 Packmol 输入、工具身份、模板、原始输出和实例映射；`parameter_assembly.json` 保存参数合并记录；`resolved_system.json` 保存请求/实际数量与初始分子数分数。原子映射同时保留组分、分子、实例组身份。内部阶段入口沿用 `build/solvated.gro` 文件名；在无水场景它仅是最终坐标文件，不表示含水。

## 可选、独立的分析

`analysis_requests: []` 完全关闭默认分析，不隐式做水化，不创建分析目录。任务支持 `hydration_contacts` 和 `component_contacts`；每个请求包含 `id / kind / stage_id / config`。可用 `analyze --request <JSON> --output-root <外部目录>` 对完成 Run 的任一已完成动力学阶段单独分析，覆盖默认列表。配置字段见示例，不需要把阶段叫 prod。

`component_contacts` 的 config 为 `component_a / component_b / cutoff_nm`，输出逐帧唯一分子对数量与计数分布。相同组分时排除分子内部接触，并去掉对称重复；一个分子对中的多个原子接触只算一次。不把接触计数称为结合自由能或平衡占有率。

每个 AnalysisRun 保存请求、当前分析实现、来源 Run/manifest、轨迹/坐标/映射副本及哈希、状态、CSV/报告。MDAnalysis 的 XTC 缓存只写在分析副本旁，不写原 Run。分析失败保留自己的 failed 状态，不改变或重跑 MD。当前复制策略只适用于受限工程轨迹，大轨迹前需设计独立缓存/分段存储。

水化是配置给定阈值的周期原子接触计数与水氧并集去重：ZIL 示例用 0.35 nm，CAT/ANI 各位点用 0.33/0.34/0.36 nm。没有平衡剔除、自相关校正、独立重复或置信区间，不能当作正式水化数、自由能或采样收敛结论。

## Run 与历史兼容

```text
Run/
├── manifest.json / resolved_spec.json
├── inputs/                         # 原始模型、协议、完整匹配的力场库
├── build/                          # 构建结果、映射、resolved_system、派生 MDP
├── stages/<显式阶段ID>/             # 编译输入、输出和带格式/角色/哈希的 stage.json
├── attempts/                       # 命令与每代 append 前输出副本
├── status.json
└── .writer.lock
外部分析根/<独立分析ID>/              # 请求、输入副本、状态、CSV/报告
```

- v1 的 [原模型](examples/zil_model.json)与[原配置](examples/zil_smoke.json)不改写。`validate` 可以检查旧配置，status/report 可以读取旧 Run，analyze 可在外部重分析；不制造历史没有记录过的 v2 字段。
- 当前实现不再新建/执行 v1 Run。需要保留旧执行行为时使用对应原始代码快照；新任务使用 v2，不并行维护第二套执行器。
- `verify_run` 验证持久化输入和输出，与当前源码是否相同无关；`verify_execution` 额外要求 v2 和当前递归源码哈希一致。引擎版本/二进制/平台也须一致；没有 force 绕过。
- 完成态读取缺文件/哈希变化会失败，不以兼容为由吞错。v2 阶段检查额外拒绝未登记输出；实际完成由力标准或检查点步数/时间、输出、数值日志共同判定。
- 完成、终止失败、硬杀后不确定状态不原地重开，不自动删锁改状态；父 Run/检查点派生 API 尚未实现。改变协议或延长已完成目标必须创建新 Run。
- POSIX 单写者仅约束同一物理目录，不是跨复制目录/机器的全局任务锁。新 Run/分析始终放源码与输入目录之外；保留整套证据，不自动删除归档。

## 验证和下一步

```sh
"$SIM_PY" -B -m unittest discover -s tests -v
```

M1 实测：37 项测试通过；两个 8,910 原子的 Mac CPU 短程 Run；真实预算中断/恢复、三种篡改拒绝、历史 21 帧一致、149 个历史文件不变、非 prod 中间阶段分析、空任务无输出、独立分析失败均通过。细节与边界见 [本轮记录](docs/2026-09-14__m1-core-acceptance.md)。

`tests/check_resume_guards.py` 只修改隔离副本；`tests/compare_analysis.py` 对当前报告对应阶段执行新旧算法对照；`tests/verify_m1_evidence.py` 检查真实 Run 和独立分析。直接运行这些脚本时需从本目录显式使用 `PYTHONPATH=.`；参数见各自 `--help`。它们不是自动发现的单元测试，不启动长 MD。

M2 实测：45 项测试通过；ZIL（8,910 原子）与 CAT/ANI（8,912 原子）各完成 8 ps；真实中断/恢复与隔离篡改拒绝通过；两套案例各 21 帧新旧算法一致。原 CAT/ANI 资产 88 个文件不变，11 个公共原子类型与独立参数化输出一致。同一新 Mac 固定帧、同有效参数的旧/新拓扑单点能量与力比较通过；不声称复现历史 Windows 数值。详见 [M2 记录](docs/2026-09-14__m2-core-reuse-acceptance.md)。

`tests/compare_pair_single_point.py` 使用两次单帧 rerun，不启动长轨迹；`tests/verify_m2_evidence.py` 读取真实 Run、原资产与哈希清单完成审计。它们与上述辅助脚本一样需要 `PYTHONPATH=.` 和显式独立输出位置，不属于自动发现的单元测试。

M3 当前子集：66 项测试通过，以上四个真实场景完成，三组分体系的实际预算中断/恢复及隔离负例通过；三个水场景各 21 帧、无水场景 11 帧与独立最小镜像算法一致。`tests/verify_m3_evidence.py` 负责真实 Run/实例映射/原资产及独立分析审计，需显式外部输出；详见 [M3 记录](docs/2026-09-14__m3-packing-subset-acceptance.md)。

下一步需选定真实混合溶剂及其完整模型，才能完成 M3a 剩余必需项；当前水仍是 bundle 覆盖的显式填充策略，尚非可与任意溶剂共同按整数数量装配的独立模板。浓度换算属于 M3b，聚合物/固相/界面属于 M4—M6。Linux/GPU、科学平衡/物性与灾难恢复均未验收。
