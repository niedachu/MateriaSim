# 单实验模拟指南

当前是原生 macOS/Linux 路线的受限工程核心，**不是已经支持任意多组分、多材料、多场景的平台**。M1/M2 及 M3 的既有模型自动装配子集在 macOS CPU 通过工程验收；混合溶剂尚缺，M3 整体未完成，M4—M6 未实施，Linux/GPU 未实测。

已有能力：独立模型/相互作用包/场景/协议/分析请求 → 冻结输入 → 预建结构或 Packmol 自动装配 → 可命名线性阶段 → 严格续跑 → 独立分析。ZIL/CAT/ANI 可按整数数量装配并加水；无水正交周期盒可做固定体积短测。聚合物、固相、纳米材料、混合溶剂和 LAMMPS 尚未实现。

M3 经授权新装原生 Packmol 21.2.3，复用现有 Python/分析环境；没有调用 PowerShell、修改 ML 环境、原模型/MDP 或历史 Run。无水专用 EM 模板另存，仅去掉无用途的水宏。详见 [M3 子集验收](../validation/2026-09-14__m3-packing-subset-acceptance.md)；[M2](../validation/2026-09-14__m2-core-reuse-acceptance.md)、[M1](../validation/2026-09-14__m1-core-acceptance.md)与[第一轮验收](../validation/2026-09-14__mac-framework-acceptance.md)保留为历史记录。

## 代码责任

| 文件 | 当前职责 |
|---|---|
| `specs/schema.py` | 严格字段校验、版本入口、真实 v1 配置的只读解析 |
| `specs/experiment.py` | v2 的模型、相互作用包、组分计数、场景和分析请求解析 |
| `specs/v3.py` | 引擎无关的 v3 文档、带格式资产、物理目标、边界与已消费的 CPU 执行配置 |
| `workflows/validation.py` | 对外 load_spec：解析资产后，调用已登记引擎/场景/分析的真实适用性检查 |
| `workflows/migration.py` / `engines/gromacs/migration.py` | 新任务的确定性 v2→v3 转换、原文来源和可审查预览；不修改旧 Run |
| `engines/gromacs/specification.py` | v3 原生适用性、格式/资产与声明物理量对照；当前 GROMACS 限制留在后端 |
| `engines/contracts.py` / `engines/registry.py` / `engines/gromacs/adapter.py` | 已实现引擎的函数契约、显式登记和原生操作适配；构建/执行工作流消费这些接口 |
| `engines/prepared.py` / `engines/gromacs/compile.py` | 编译交接契约验证；GROMACS 输入闭包、前驱状态、编译及原生准备记录 |
| `builders/contracts.py` / `scenarios/registry.py` | 构建交接与持久化产物核对；已有场景描述和来源校验 |
| `builders/registry.py` / `scenarios/planning.py` | 登记真实预建/装填构建器，生成并消费初版构建规划 |
| `analysis/registry.py` / `analysis/contracts.py` | 两类真实分析器、角色/格式输入与共同结果封装，不在核心编排中选择具体算法 |
| `capabilities.py` / `errors.py` | 从实际登记生成能力查询与稳定机器错误，不推断 GPU 或科学验收通过 |
| `engines/gromacs/prebuilt.py` | 固定混合结构的数量、原子顺序、模型连接与预处理后一致性；不执行自动装填 |
| `builders/regions.py` / `specs/composition.py` | 引擎无关的区域/数量校验和显式组成 |
| `scenarios/packed.py` | 当前装配场景的组装、模型和无水协议约束 |
| `engines/gromacs/parameters.py` / `engines/gromacs/coordinates.py` | 显式 GAFF 参数合并与 GRO 输出；不承担通用区域校验 |
| `builders/packmol.py` / `runtime/process.py` | Packmol 模板/几何/PBC 检查；共用有界原生进程调用，不依赖 GROMACS 环境 |
| `engines/gromacs/packed.py` | 自动装配与同一 GROMACS 核心的交接，可加水或无水；不复制 runner |
| `specs/protocol.py` / `engines/gromacs/mdp.py` | 阶段 ID/继承/目标约定与 GROMACS MDP 绑定/派生分开 |
| `workflows/build.py` / `workflows/execute.py` | Run 与线性协议编排，不解释 GROMACS 输出 |
| `engines/gromacs/build.py` / `engines/gromacs/topology.py` | 当前水盒构建器、力场库冻结、实际组成/原子映射 |
| `engines/gromacs/stage.py` / `engines/gromacs/command.py` | 消费已编译契约执行/恢复、完成检查与原生检查点；执行器不再隐式编译 |
| `storage.py` / `runtime/state.py` / `runtime/records.py` | 内容身份、单写者、版本化读取、执行兼容和产物引用 |
| `runtime/identity.py` / `runtime/budget.py` | 操作源码依赖闭包、物理/资源/分析身份分离与跨 attempt 执行计费 |
| `specs/execution.py` / `runtime/control.py` | profile v2 的全流程预算与独立控制账本；单实验和研究共用 |
| `runtime/journal.py` | 控制账本版本、请求/结果哈希、事件顺序、计费与输出清单的只读校验 |
| `engines/gromacs/device.py` | CPU/单 CUDA GPU 候选参数、设备 UUID 与原生卸载报告检查，不代替硬件验收 |
| `specs/analysis.py` / `workflows/analysis.py` / `analysis/hydration.py` / `analysis/component_contacts.py` | 共享分析请求、独立调度、水化接触和唯一分子对接触 |
| `cli.py` / `__main__.py` | `python -m materiasim` 入口 |

这些文件均在 `src/materiasim/` 下。只实现当前具体 GROMACS 适配器，没有空后端、插件工厂或第二套执行核心。

Python 只读校验使用 `materiasim.workflows.validation.load_spec`，返回所读格式及完整适用性检查结果。创建新任务使用 `workflows.migration.load_executable`，将 v2/v3 统一解析成 v3 并返回来源报告。`specs.schema.read_spec` 仅解析格式/资产，不能代替适用性检查；不保留第二套旧执行器。

当前可安装核心为 `src/materiasim/`，共享资产在 `catalog/`，研究编排见[研究指南](research.md)。A—D 历史验收保持原记录；最新进度见[可扩展框架方案](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)。profile v2 增加全流程控制与 GPU 候选路径；profile v3 增加冻结工具定位与有限非短测配置，正式用途需要下述明确证据。

## 环境与最短用法

从仓库根执行；本机复用 Python 3.9.25、GROMACS 2026.3-Homebrew、MDAnalysis 2.7.0、NumPy 1.26.4。核心仅用标准库；分析依赖后两者。开发环境先安装本项目，安装后其他工作目录可直接调用 `materiasim`。未安装时从仓库根使用 `PYTHONPATH=src python -m materiasim`。Linux 使用自己的本地环境，不能复制 Mac 虚拟环境/二进制。

```sh
SIM_PY='python' # 当前已安装 MateriaSim 与分析依赖的环境
"$SIM_PY" -B -m materiasim doctor
"$SIM_PY" -B -m materiasim validate examples/zil_smoke_v2.json

# 临时工程证据，不是长期科研归档。
SIM_RUN_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/materials-smoke.XXXXXX")"
SIM_RUN="$("$SIM_PY" -B -m materiasim build examples/zil_smoke_v2.json \
  --run-root "$SIM_RUN_ROOT" | "$SIM_PY" -c 'import json,sys; print(json.load(sys.stdin)["run_dir"])')"

"$SIM_PY" -B -m materiasim run "$SIM_RUN" --threads 2 --max-wall-seconds 180
"$SIM_PY" -B -m materiasim status "$SIM_RUN"
```

状态为 `interrupted` 才用 `resume` 继续原目标，不重新 `run`：

```sh
"$SIM_PY" -B -m materiasim resume "$SIM_RUN" --threads 2 --max-wall-seconds 180
```

状态为 `completed` 后，分析写到显式指定的 **Run 外部** 目录：

```sh
"$SIM_PY" -B -m materiasim analyze "$SIM_RUN" --output-root "$SIM_RUN_ROOT/analyses"
"$SIM_PY" -B -m materiasim report "$SIM_RUN" --analysis-root "$SIM_RUN_ROOT/analyses"
```

`doctor / capabilities / validate / migrate / status / report` 是只读查询，不生成 Run 或启动 MD。`validate` 检查配置/资产；`executable=true` 只表示已实现的子集，不代替实际工具、`grompp` 或科学验收。`migrate` 返回转换后的实验和来源报告，不保存配置。`build` 可调用 Packmol/editconf/solvate/grompp，但不积分动力学。

自动装配额外需要原生 Packmol ≥21.1.0，使用其可回读文件的 `-i` 接口。已验收版本为 21.2.3；没有自动安装或替代构建器。`doctor --packmol packmol` 查询版本/哈希，`capabilities` 列出真实能力及未实现项，`build --packmol /path/to/packmol` 可指定程序。已构建 Run 的续跑不重新装填，不依赖当前 Packmol 版本。

`capabilities` 当前输出契约为 `contract_version: 1`，engines/scenarios/analysis 为带 ID 与约束的记录列表，来源是执行时使用的同一登记表。它不探测设备，`environment: not_checked` 不代表工具缺失或可用；历史工程记录不自动适用于当前源码修订。

CLI 失败时向 stderr 输出 JSON、返回非零：包含 `contract_version`、`ok: false` 和 `error`。错误包含 code/category/message/field/evidence_refs/recoverability；参数语法错误为 INVALID_ARGUMENT，缺输入文件为 MISSING_RESOURCE，缺原生工具为 MISSING_DEPENDENCY，未实现组件为 UNSUPPORTED_COMBINATION，源码变化导致的恢复拒绝为 RESUME_INCOMPATIBLE。尚未细分的既有验证/执行错误分别为 INVALID_SPEC/OPERATION_FAILED；不根据错误文本猜测恢复权限。`--help` 仍为普通帮助文本与成功退出。

`--gmx` 可用于 doctor/build/run/resume。`--through` 接受当前配置中的阶段 ID；默认终点是最后一个阶段，不固定为 prod。`run/resume` 默认读取冻结的执行配置；`--threads` 只能与配置一致，`--max-wall-seconds` 只能缩短单次上限，不能借命令参数增配额。调整配置须创建新 Run。

CPU 执行配置 contract_version=1：线程 1—8、单次 1—600 秒、累计最多 1800 秒、attempt 上限 1—8、检查点间隔 .001—10 分钟。v2 迁移策略明确设为 2 线程、单次 180 秒、累计 360 秒、最多 2 次、检查点 .01 分钟；不是沿用未知历史资源。分配下一次预算时先预留 25 秒退出宽限，再按实际执行计费。`execution.json` 与实际 attempt 对应，删除账本或不确定交接不能重新获得预算。

工作流显式调用 `prepare_stage` → `run_stage`，传递 PreparedStage。准备后重算剩余时间，耗尽则不启动新的 mdrun。原 profile v1 的跨 attempt 账本只涵盖执行中的编译/验证/积分/退出；build/analysis 不计入 v1 总额。新 profile v2 另有下述全流程控制；两者都不是 OS 硬配额。

## 全流程执行配置 v2 与 GPU 候选路径

原生 v3 示例中的 execution_profile.contract_version 可显式采用 2，其他 v3 字段语义不变。可直接参考[双场景研究实验](../../studies/mixed_builders_smoke/experiments/prebuilt.json)的 CPU 配置；它也能用普通 build/run/analyze 命令运行，不要求进入研究包。

保留 v1 的线程、单次/累计执行、attempt 与检查点字段，额外要求：

- build_seconds、analysis_seconds、workflow_seconds：构建、一次分析调用、全流程墙钟总额。
- termination_grace_seconds：25—60 秒退出宽限，授予下一操作前预留。
- storage_bytes、min_free_bytes：输出停止阈值和磁盘安全余量。
- gpu_id、dynamics_offload：明确设备与 nb/pme/bonded/update 策略，不接受 auto 或 shell 参数。

profile v2 的 build/run/resume/analyze 全部使用同一监督器，操作前预留、结束后记实耗。CPU v2 每项卸载旗标明确为 cpu。Run 同级 `.materiasim-operations/<RunID>/` 保存控制身份、请求、标准输出/错误、结果与账本，manifest 绑定其 ID；控制账本缺失、未闭合交接或记录不一致拒绝继续。分析预算写在控制目录，不改变已完成 MD Run。归档/移动时须保留 Run、控制目录及分析结果；目前已记录的分析目录仍是显式路径，跨位置续跑不是自动迁移服务。

新的控制账本 `contract_version=2` 与 execution_profile v2 是两个独立版本。每个操作保存请求哈希、顺序号、前次结算哈希、结果哈希和实测结算；工作进程接受请求前、监督器结算后及授予下一操作前都核查。负数/非有限计费、布尔值冒充数值、请求或结果变化、缺失/多余事件目录、顺序不符、停止状态矛盾和分析输出清单不符均拒绝。未闭合的最后一项保留完整预扣，不自动修复或重置。

历史控制账本 v1 保持原样并支持只读核查，但不向它追加新的 build/run/resume/analyze 操作，也不补造请求/结果哈希。这一限制针对带旧全流程账本的 profile v2 Run；不改变无此账本的历史 v1/v2 Run 原有只读/外部分析路径。需要重做旧账本所控制的操作，应保留历史并使用匹配的源码快照，或从原配置建立新的独立 Run；目前没有原地升级或预算迁移命令。

控制账本哈希用于发现证据损坏和不一致，不是签名、审批或防管理员改写的安全边界。日志全文不在该哈希链中，文件系统/硬件损坏、强杀回收和复制迁移仍需独立保障。

监督器周期检查已登记输出目录和磁盘。新分析调用先分配 `operation-<唯一ID>/` 私有命名空间，账本仅登记并计入它，不把共享父目录内其他 Run 的分析计入本次预算；历史平铺 AnalysisRun 仍可只读查阅。采样和退出宽限可能越过停止阈值，不是文件系统硬配额。大轨迹负载仍未验收。

任务退出后还会检查墙钟、目录字节和磁盘余量，避免极短操作在两次采样之间结束而漏检；即使退出码为零，超预算也不判为成功。存储根本身及其父路径不允许符号链接，但这不等于操作系统级目录隔离或硬配额。

[GPU 候选示例](../../examples/v3/packed_zil_water_gpu.json)可只读 validate，**不代表本机可执行**。当前候选仅实现单 CUDA GPU、一个 thread-MPI rank，动力学 nb=gpu、pme 可选 cpu/gpu，bonded/update 仍 cpu；最小化全部 cpu。不支持 AMD/Intel/Apple GPU、MIG 或多 GPU，也不安装 CUDA/驱动。

`materiasim doctor --devices` 只读查询构建信息及可选 NVIDIA 驱动清单，缺查询工具或未知格式报告 unknown。gpu_id 指过滤 CUDA_VISIBLE_DEVICES 后的驱动清单位置；目前只接受完整 GPU UUID 或驱动整数索引的可见列表。子进程用选中 UUID 限定 CUDA 可见性，再向 GROMACS 传入本地设备 0，不改变全局环境。执行检查构建、设备和线程，并核对当次原生启动报告的 PP/PME 映射与实际卸载；缺证据拒绝成功，不静默回退 CPU。

参数与检查点依据 [GROMACS mdrun 文档](https://manual.gromacs.org/documentation/current/onlinehelp/gmx-mdrun.html)，任务映射依据[性能指南](https://manual.gromacs.org/documentation/current/user-guide/mdrun-performance.html)，设备清单依据 [NVIDIA nvidia-smi 文档](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。日志识别仍需目标服务器实际版本验收；现有模板、短程限制与 engineering_only 模型没有因 GPU 配置开放而改变。

## 用途证据、采样和执行配置 v3

Experiment/Run 仍为 schema_version=3；只有此前未开放的非 smoke 用途新增显式嵌套契约，不重新解释旧 smoke 文档。

| 用途 | 进入条件 | 不能据此声称 |
|---|---|---|
| engineering_smoke | 原短程、有限规模和全部结构/参数检查 | 模型已科学验证 |
| model_validation | 明确目标、参数审查、协议审查与验证设计证据，profile v3、显式采样和目标环境绑定 | 运行完就完成模型验证 |
| production | 参数/协议审查与适用范围验证证据；bundle 为 reviewed，模型来源、分辨率、组分角色均明确 | 字符串或软件测试证据能代替真实审核 |

非 smoke 实验必须增加 `purpose_policy`，字段为：contract_version=1、intent、reviewer、带时区 reviewed_utc、target_hash、environment、evidence、files。

- `target_hash` 使用 `materiasim.specs.purpose.target_hash(spec)` 计算；覆盖物理设计、参数资产、组成、用途和采样，排除 id、分析请求、资源以及显式重复种子。更改模型/数量/协议需新的对应审核，不改原证据。
- `environment` 精确声明 platform（darwin/linux）、engine_version、engine_sha256；build 和 execute 均与实际 GROMACS 核对。审核针对该环境，不自动跨平台适用。
- `evidence` 将角色映射到三个不同的逻辑资产名。model_validation 的角色为 parameter_review/protocol_review/validation_design；production 将最后一项换为 applicability_validation。
- `files` 按普通 v3 资产记录 name、format=json、sha256 与 source；文件随输入冻结。每份 JSON 要求 contract_version=1、kind（角色）、decision=accepted、target_hash、reviewer、basis、limitations。目标与审核人必须对应策略，依据和局限不得为空。

这是**本地人工审核声明的可追溯契约，不是身份认证或电子签名**。程序检查内容绑定与硬约束，不判断文献证据是否真的足够，也不能防有写权限者一致重写声明。现有 catalog 没有因此被授予 production；测试数据见 `tests/unit/test_purpose_storage_delivery.py`，明确标记 SOFTWARE TEST，不能复制为真实批准。

每个非 smoke 阶段必须额外声明 `sampling={contract_version:1, log_steps:整数, energy_steps:整数, trajectory_steps:整数}`，间隔范围 1—本阶段 steps；实际用于派生 MDP 的 nstlog/nstenergy/nstxout-compressed，包括最小化。全精度坐标/速度/力输出流必须关闭，当前不承诺这些额外数据流。原 smoke 模板及覆盖语义保持。

profile v3 在 v2 全部字段上新增 `tools={gmx:可执行文件名或路径, packmol:可执行文件名或路径}`；不是 shell 命令。单实验默认使用冻结定位器；显式 CLI --gmx/--packmol 必须完全匹配。研究 CLI 当前仍默认 gmx/packmol，使用其他定位器时须显式传入匹配值。

v3 各项墙钟配置最多 604800 秒、storage_bytes 最多 1 TiB；有限数值和累计/宽限校验仍生效，线程仍最多 8、attempt 最多 8。这只是配置上限，**不是经过长负载验收的容量承诺**。非 smoke 不再套用 MD 2000 步的 smoke 上限，但保持正整数及原生步数范围、2—8 个线性阶段、dt≤0.002 ps、20,000 原子及当前盒子/组分/构建限制。执行前按声明采样、现有原子上限及副本代数估算容量，含最小化；估算具有不确定性，运行时仍监视实际字节。

## 副本、进程清理与可搬迁只读归档

`runtime/capacity.py` 在快照、封存、分析输入和计划复制前计量源文件字节，并检查已登记输出、复制增量及磁盘余量。采用独立普通副本，不用硬链接保存可变轨迹；复制前后校验源与目标哈希，失败保留现场、不自动清理或覆盖目标。

新 Run manifest 的 storage_contract=1 要求每个 stage.json 保存 archive_generations：每代记录 contract_version=1、attempt 下的相对目录及哈希。中断后 append 只更新活动文件，旧代副本独立；代次清单遗漏、重复、缺文件或内容变化均拒绝。旧 Run 没有此契约时不补造历史证明。

最外层存活的监督器拥有独立进程组，正常退出或强杀时回收同组残留后代；内层 worker 不另建脱离监督的原生组。单元测试实际启动并回收隔离后代进程。最外层监督器本身遭 SIGKILL、机器掉电、恶意子进程主动逃逸会话不在此保证内；账本保持未闭合并拒绝自动重试，服务器级回收须另用调度器/cgroup。保留 25—60 秒宽限和磁盘余量，不宣称硬配额或全系统灾备。

导出必须是完成态 Run 和显式新路径、字节预算：

```sh
materiasim --json-envelope archive "$SIM_RUN" --output /实际新路径/证据包 --max-bytes 134217728
materiasim --json-envelope verify-archive /实际新路径/证据包
```

证据包包含 Run、其绑定的已闭合控制账本、该账本登记的全部分析，并保存相对文件哈希和原路径来源。verify-archive 只读取包内副本，验证 Run、账本、报告/CSV/冻结分析输入；原始路径不是读取依赖。普通复制到新位置后可再次核查，原文件不动；任何失败副本保留，不能当成功备份使用。旧 profile v1 无全流程账本，无法自动发现外部分析；其未登记分析、Research 计划/比较/批次账本以及包外科研资料必须另外保存。

只读归档不等于活动路径迁移：无 rebind/force 命令、不改原请求、不扩大余额、不提供 Mac→Linux 检查点续跑。归档验证也不是防管理员篡改的签名服务；极大单轨迹、多副本成本、断电恢复及异地存储可靠性仍需专门验证。

## Agent 调用和组件扩展

`materiasim tools` 查询真实命令及读写分类。需要统一响应时将 `--json-envelope` 放在子命令前：成功返回 `{contract_version:1, ok:true, action:命令, result:原结果}`；错误沿用现有结构化 stderr 与非零退出码。未加旗标的历史成功输出不变。plan 默认只预览，archive/build/run/analyze 写入，verify-archive 只读；无任意脚本执行配置或外部 LLM 服务。

扩展优先从已有可工作的组件复制其**接口职责**，不复制 workflow：

1. 新分析器参照 `analysis/registry.py` 的 Analyzer 与两个实际算法：实现配置验证、calculate(inputs, config, output, identity)、输入角色/格式、结果文件哈希、指标单位和 observations。先用私有输入与已知答案测试，再登记到 ANALYZERS；缺轨迹角色应在创建输出前拒绝。
2. 新构建能力参照 `builders/registry.py`、`scenarios/planning.py` 和现有 native builder：返回实际 BuildResult，产出 mapping/resolved_system，接受 validate_result 的数量/身份/资产核查。不改 research worker 来塞一个特别分支。
3. 新引擎参照 `engines/gromacs/adapter.py` 的 EngineAdapter：实现 validate/inspect/build/prepare_stage/run_stage；PreparedStage 带角色、格式、有效参数、依赖闭包和引擎身份，StageEvidence 只报告完成/中断。还须实现该引擎的 seal、artifact 和恢复核查；当前 `runtime/state.py` 含 GROMACS 产物约束，**仅登记 ID 不能接入另一个引擎**。
4. 单测范例见 `tests/unit/test_component_boundaries.py`：替换登记组件后验证工作流真实消费它，缺能力明确拒绝。新真实能力要补相应小量原生验收；测试夹具不进入用户能力清单。

研究源码包仍使用 studies/<id>/README.md、research.json、experiments/，共享参数放 catalog；发行包仅带核心代码，不把个人模型/历史输出塞入 wheel。把独立研究输入或冻结计划与核心分别交付，在仓库外用同一 CLI 验证与执行。

## v3 当前格式与迁移

[packed_zil_water.json](../../examples/v3/packed_zil_water.json) 是完整、可校验的 v3 示例。v3 内嵌模型/包/协议描述，资产仍按相对配置路径的 `source`、逻辑 `name`、`format`、`sha256` 引用；解析后的内容身份不包含 source 路径。

| 边界 | 当前字段及语义 |
|---|---|
| 组分与模型 | components 的 id/model/count/role；模型声明 resolution、provenance、坐标/拓扑资产引用，不从名称猜化学来源 |
| 相互作用包 | 精确 model_hashes、engine、engine_parameters、validation_scope、公共资产；哈希不是科学适用证明 |
| 场景 | kind、boundary.vectors_nm、boundary.periodic、builder.id/config；现有后端只接受正交三维周期盒 |
| 协议 | 阶段 type、steps、input、velocities/seed、时间原点、physics、outputs 与 engine_parameters 的资产引用 |
| 物理声明 | timestep_ps、temperature_k 列表、pressure_bar 列表、force_tolerance_kj_mol_nm；与实际 MDP 核对，不隐式覆盖 |
| 执行 | 独立 execution_profile；v1 保留 CPU 语义，v2 使用全流程控制与受限单 CUDA GPU 候选策略，不降级执行 |

迁移不补造旧模型的分辨率、用途角色或文献来源：缺失值保留 unspecified/not_provided。现有 catalog 仍是 engineering_only；production 必须满足证据、来源、角色及相互作用包适用性门禁，不能只改字符串。

构建规划保存在 `build/plan.json`，由实际登记的 gromacs_prebuilt 或 gromacs_packmol 消费。初版每例是一个完整的原生构建流水线步骤；初始 EM 预处理用于原子映射核查。不宣称任意步骤 DAG、自动聚合物构建或任意场景拼接已经实现。

| 对象 | 当前策略 |
|---|---|
| v1 实验/Run | 保留既有只读检查与有条件外部重分析，不新建或执行 |
| v2 实验 | 可校验、只读 migrate 预览，build 时确定性转换并创建新 v3 Run |
| v2 Run | 只读，不补写字段，不由当前代码执行或恢复 |
| v3 实验/Run | 唯一新执行格式；冻结资源、来源报告、分层身份和阶段准备记录 |
| Research 源码/冻结计划 | 定义 v1/v2；新冻结计划版本 3、任务为 v3；旧计划版本 1/2 只读，详见研究指南 |

## 既有 v2 输入与实际支持子集

ZIL 示例是 [zil_smoke_v2.json](../../examples/zil_smoke_v2.json)，引用：

- [zil_model_v2.json](../../catalog/models/zil_model_v2.json)：ZIL 身份与预建坐标/拓扑/参数文件哈希；没有 MDP 或实验分子数量。
- [zil_bundle.json](../../catalog/interaction_bundles/zil_bundle.json)：精确模型内容哈希、GROMACS 力场目录与库文件内容哈希、TIP3P、`engineering_only` 范围。此记录不是任意力场混搭的批准书。
- [zil_protocol.json](../../catalog/protocols/zil_protocol.json)：原始 MDP 的来源/哈希和有序阶段；不修改源模板。

CAT/ANI 示例是 [cat_ani_smoke.json](../../examples/cat_ani_smoke.json)，引用独立的 [CAT 模型](../../catalog/models/cat_model.json)、[ANI 模型](../../catalog/models/ani_model.json)、[相互作用包](../../catalog/interaction_bundles/cat_ani_bundle.json)与[协议](../../catalog/protocols/cat_ani_protocol.json)。把上述 build/validate 命令的配置路径换成该示例即可使用同一入口。

该场景读取原案例的 41 原子干态 `pair_initial.gro`，保持溶质坐标与 4.5 nm 盒不变，加水后严格检查 CAT 1＋ANI 1＋SOL 2957。它是新 Mac 工程水盒，不是缺失的旧 Windows 含水坐标/轨迹复现。`solvent_count` 通过 `solvate -maxsol` 后检查实际计数；不是浓度换算或平衡密度承诺。

补查发现旧 CAT/ANI 入口重新加水不保证逐字节复现：本机 GROMACS 2026.3 在超出 `-maxsol` 时随机删水，两次构建各有一个不同的水分子，计数/溶质/拓扑不变。精确历史初态应读取冻结产物，不能重新加水替代。新 `packed_liquid` 填水不使用 `-maxsol`，四个固定种子重建坐标比较通过；这是本机实测，不是跨版本保证。详见 [诊断记录](../validation/2026-09-14__m3-packing-subset-acceptance.md#旧入口回归的已知限制)。

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
| [packed_zil_water.json](../../examples/packed_zil_water.json) | ZIL×2＋水，同一模型分别放入 left/right 两个初始区域 |
| [packed_ions_water.json](../../examples/packed_ions_water.json) | CAT×2＋ANI×2＋水，多副本及电中性检查 |
| [packed_mixture_water.json](../../examples/packed_mixture_water.json) | ZIL＋CAT＋ANI＋水，三种非溶剂共同装配 |
| [packed_zil_dry.json](../../examples/packed_zil_dry.json) | ZIL×2、无水周期盒，EM＋固定体积 NVT 短测；不代表固体/熔体 |

例如：`"$SIM_PY" -B -m materiasim validate examples/packed_mixture_water.json`。

v2 的 `scenario.groups`（v3 的 `scenario.builder.config.groups`）每组包含唯一 `id`、已声明 `component_id`、正整数 `count` 和三维 `min_nm/max_nm`。同一模型可在多组出现，各组计数之和必须等于 components 总数。`solvent_fill` 是自动水组保留 ID。区域只约束初始装填，不是动力学约束或界面制备。下述 seed/tolerance/solvent 等构建选项在 v3 也位于 builder.config。

`seed` 为装填种子，独立于协议速度种子；`tolerance_nm` 为分子间目标原子距离，`max_iterations` 为有限 Packmol 优化循环数。仅一次固定种子尝试，最多 60 秒，不自动重试、减数量或扩盒。Packmol 精度固定为 1e-6；输出按 0.001 nm GRO 精度检查，几何/区域误差上限 0.002 nm，同时核对周期最小镜像距离。

`solvent.kind` 仅支持 `tip3p_fill` 或 `none`。前者用已冻结 TIP3P/水库填充剩余空间，记录实际水数和分子数分数，不保证指定浓度；后者不加水且当前要求固定体积协议、禁止水化任务。[dry_em.mdp](../../catalog/protocols/dry/dry_em.mdp) 来自原 ZIL EM，只去掉无水时无用途的 `-DFLEXIBLE`；原文件不变。

装配子集最多 2,000 个非溶剂原子，要求显式电中性（仅容许既有序列化舍入残差）、连通单分子、明确逐原子电荷质量及当前 GAFF 键合形式。用户分子文件中的宏/include、缺失类型、同名类型不同参数、隐式键合项均拒绝。公共类型去重及分子 ITP 派生只写 Run 的 `build/`，保留原文件与转换哈希，并用原生展开拓扑逐项核对。

`build/packing/` 保存 Packmol 输入、工具身份、模板、原始输出和实例映射；`parameter_assembly.json` 保存参数合并记录；`resolved_system.json` 保存请求/实际数量与初始分子数分数。原子映射同时保留组分、分子、实例组身份。内部阶段入口沿用 `build/solvated.gro` 文件名；在无水场景它仅是最终坐标文件，不表示含水。

## 可选、独立的分析

`analysis_requests: []` 完全关闭默认分析，不隐式做水化，不创建分析目录。任务支持 `hydration_contacts` 和 `component_contacts`；每个请求包含 `id / kind / stage_id / config`。可用 `analyze --request <JSON> --output-root <外部目录>` 对完成 Run 的任一已完成动力学阶段单独分析，覆盖默认列表。配置字段见示例，不需要把阶段叫 prod。

`component_contacts` 的 config 为 `component_a / component_b / cutoff_nm`，输出逐帧唯一分子对数量与计数分布。相同组分时排除分子内部接触，并去掉对称重复；一个分子对中的多个原子接触只算一次。不把接触计数称为结合自由能或平衡占有率。

每个 AnalysisRun 保存请求、当前分析实现、来源 Run/manifest、轨迹/坐标/映射副本及哈希、状态、CSV/报告。MDAnalysis 的 XTC 缓存只写在分析副本旁，不写原 Run。分析失败保留自己的 failed 状态，不改变或重跑 MD。当前复制策略只适用于受限工程轨迹，大轨迹前需设计独立缓存/分段存储。

新生成报告保留原 CSV 和算法数值字段，并增加 `result_contract`，明确方法、来源 Run/规格、请求哈希、方法依赖版本、帧数与 ps 时间范围。两个当前分析器都需要坐标、轨迹和原子映射；这不是任意性质分析已实现，也没有增加统计独立性或置信区间计算。

水化是配置给定阈值的周期原子接触计数与水氧并集去重：ZIL 示例用 0.35 nm，CAT/ANI 各位点用 0.33/0.34/0.36 nm。没有平衡剔除、自相关校正、独立重复或置信区间，不能当作正式水化数、自由能或采样收敛结论。

## Run 与历史兼容

```text
Run/
├── manifest.json / resolved_spec.json
├── inputs/                         # 原始模型、协议、完整匹配的力场库
├── build/                          # 构建结果、映射、resolved_system、派生 MDP
├── provenance/                     # 原文快照与迁移报告，纳入冻结清单
├── stages/<显式阶段ID>/             # 编译输入、输出和带格式/角色/哈希的 stage.json
├── attempts/                       # 命令与每代 append 前输出副本
├── execution.json                  # 有界执行 attempt 预留与实际计费
├── status.json
└── .writer.lock
外部分析根/<独立分析ID>/              # 请求、输入副本、状态、CSV/报告
```

- v1 的 [原模型](../../catalog/models/zil_model.json)与[原配置](../../examples/zil_smoke.json)不改写。`validate` 可以检查旧配置，status/report 可以读取旧 Run，analyze 可在外部重分析；不制造历史没有记录过的 v2 字段。
- v3 `stage.json` 必须含 `preparation.contract_version: 1`：记录阶段描述、带格式的输入/编译产物、派生 MDP 有效参数、完整冻结原生查找树和前驱输入哈希、引擎身份。`resolved.mdp` / `processed.top` 是编译器实际输出，不把派生参数字典当成完整解析后的 TPR。
- 编译前驱必须已完成，坐标/检查点匹配封存；编译期间输入变化不发布成功准备记录。恢复复用原准备记录及 TPR，不重新编译。缺少准备记录的旧 v2 阶段保持只读，不推断补写。
- 新 Run 的 `provenance/source_documents/` 保存原文，`provenance/migration.json` 记录源/目标版本、原文哈希、转换与解析身份；不向 inputs 追加会改变已编译闭包的来源文件。
- 当前不新建/执行 v1/v2 Run。旧执行如需继续须使用对应原始代码快照；v2 输入则经适配新建 v3，不并行维护旧 runner。
- `verify_run` 验证持久化输入和输出，与当前源码无关；`verify_execution` 额外要求 v3 和执行源码依赖闭包一致，包括编译、进程、状态、存储、资源模块及其传递依赖。分析算法独立改动不再必然阻断恢复；共有依赖改动仍保守拒绝。引擎版本/二进制/平台须一致，没有 force 绕过。
- manifest 分开冻结物理输入、构建结果、执行实现/资源、分析请求身份；整体源码仍留作诊断，AnalysisRun 另记当次分析实现闭包和依赖。完成态缺文件/哈希变化失败，v2/v3 拒绝未登记阶段输出；完成由力标准或检查点步数/时间、输出、数值日志共同判定。
- 完成、终止失败、硬杀后不确定状态不原地重开，不自动删锁改状态；父 Run/检查点派生 API 尚未实现。改变协议或延长已完成目标必须创建新 Run。
- POSIX 单写者仅约束同一物理目录，不是跨复制目录/机器的全局任务锁。新 Run/分析始终放源码与输入目录之外；保留整套证据，不自动删除归档。

## 验证和下一步

最新本地框架交付：193 项测试、16 个 Mac CPU Run、58 个阶段通过，包含既有十四任务、一个 model_validation 软件夹具和一个安装态独立小任务；归档搬迁/损坏拒绝、已安装包分析与历史输入保护均有记录，详见[本轮验收](../validation/2026-09-15__framework-local-delivery-acceptance.md)。此前[账本](../validation/2026-09-15__control-journal-integrity-acceptance.md)、[研究/资源](../validation/2026-09-15__research-execution-acceptance.md)、[v3](../validation/2026-09-15__v3-contracts-acceptance.md)、[编译交接](../validation/2026-09-15__prepared-stages-acceptance.md)和下方 M1—M3 保留历史事实。

```sh
PYTHONPATH=src "$SIM_PY" -B -m unittest discover -s tests -v
```

M1 实测：37 项测试通过；两个 8,910 原子的 Mac CPU 短程 Run；真实预算中断/恢复、三种篡改拒绝、历史 21 帧一致、149 个历史文件不变、非 prod 中间阶段分析、空任务无输出、独立分析失败均通过。细节与边界见 [本轮记录](../validation/2026-09-14__m1-core-acceptance.md)。

`tests/acceptance/check_resume_guards.py` 只修改隔离副本；`tests/acceptance/compare_analysis.py` 对当前报告对应阶段执行新旧算法对照；`tests/acceptance/verify_m1_evidence.py` 检查真实 Run 和独立分析。直接运行这些脚本时需从仓库根显式使用 `PYTHONPATH=src`；参数见各自 `--help`。它们不是自动发现的单元测试，不启动长 MD。

M2 实测：45 项测试通过；ZIL（8,910 原子）与 CAT/ANI（8,912 原子）各完成 8 ps；真实中断/恢复与隔离篡改拒绝通过；两套案例各 21 帧新旧算法一致。原 CAT/ANI 资产 88 个文件不变，11 个公共原子类型与独立参数化输出一致。同一新 Mac 固定帧、同有效参数的旧/新拓扑单点能量与力比较通过；不声称复现历史 Windows 数值。详见 [M2 记录](../validation/2026-09-14__m2-core-reuse-acceptance.md)。

`tests/acceptance/compare_pair_single_point.py` 使用两次单帧 rerun，不启动长轨迹；`tests/acceptance/verify_m2_evidence.py` 读取真实 Run、原资产与哈希清单完成审计。它们与上述辅助脚本一样需要 `PYTHONPATH=src` 和显式独立输出位置，不属于自动发现的单元测试。

M3 当前子集：66 项测试通过，以上四个真实场景完成，三组分体系的实际预算中断/恢复及隔离负例通过；三个水场景各 21 帧、无水场景 11 帧与独立最小镜像算法一致。`tests/acceptance/verify_m3_evidence.py` 负责真实 Run/实例映射/原资产及独立分析审计，需显式外部输出；详见 [M3 记录](../validation/2026-09-14__m3-packing-subset-acceptance.md)。

下一步接入真实混合溶剂时需完整模型，才能完成材料方案 M3a；当前水仍是 bundle 覆盖的填充策略，尚非任意溶剂共同装配的独立模板。浓度换算属于 M3b，聚合物/固相/界面属于 M4—M6；这些不属于本次框架收口。Linux/GPU、科学平衡/物性、服务器灾备、长轨迹负载仍待验收。
