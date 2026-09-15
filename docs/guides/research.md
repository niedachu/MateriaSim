# 研究包使用指南

研究源码按 `studies/<id>/README.md`、`research.json`、`experiments/` 组织，调用同一个模拟核心，不复制构建器或 runner。通用 v2 示例是 [mixed_builders_smoke](../../studies/mixed_builders_smoke/README.md)；原 [zil_count_smoke](../../studies/zil_count_smoke/research.json) 保留为 v1 来源。

## 已实现范围

- 新研究定义 `schema_version=2`，至少两个显式条件、最多 16 个任务、串行执行；单任务资源使用普通实验中的 execution_profile v2/v3。研究 purpose 必须与每个任务一致；model_validation/production 的每个任务都需通过普通实验的用途门禁，不由研究判据代替审批。
- 已有预建水盒、自动装填水盒/无水周期盒可进入同一研究编排，但必须通过原模型和场景适用性检查，不放宽科学输入约束。
- 每个 case 引用完整实验，repeat 为 `id` 和 `seeds`。装填场景需要 `packing`；每个生成速度的阶段需要 `velocity_<阶段ID>`。预建场景没有 packing 槽，继承阶段没有速度种子槽；缺槽、额外槽、重复赋值、隐式随机值均拒绝。
- 有意变化字段为 component_counts/scenario/protocol。声明变化只控制可比性检查，不会覆盖实验参数；模型、分析选择和未声明条件仍需一致。不同协议的结果还必须通过方法自身的阶段/时间窗检查，不自动合并。
- 允许无分析（实验 analysis_requests=[]、研究 observables=[]），也允许同时配置原水化接触与组分接触。每项 observable 明确 request_id/method/metric/unit，并精确覆盖配置请求。

| 方法 | 当前可比较指标 | 单位 |
|---|---|---|
| component_contacts | mean_unique_molecule_pairs | molecule_pairs |
| hydration_contacts | mean_union_water_contacts | water_molecules |

水化指标是原算法的水氧接触并集均值，不是热力学水化数。其他位点统计仍保留在各自报告；当前比较器不把两种方法混算。原 v1 研究定义保留 packed/单接触指标限制，新冻结时仍保留其原文与版本，不将 v1 文字判据伪造成科学批准。

## 预检和冻结

以下命令使用已经安装本包的环境；从仓库根指定研究源码。预览不调用 Packmol/GROMACS，也不生成 Run。

```sh
materiasim research validate studies/mixed_builders_smoke/research.json
materiasim research plan studies/mixed_builders_smoke/research.json
```

保存必须显式指定一个尚不存在的仓库外目录：

```sh
materiasim research plan studies/mixed_builders_smoke/research.json --output /private/tmp/materiasim-study-plan
materiasim research run /private/tmp/materiasim-study-plan --output-root /private/tmp/materiasim-study-batches
```

路径只是示例，不能覆盖已有计划。当前输出校验拒绝符号链接组件；macOS 临时路径使用 `/private/tmp` 而不是 `/tmp`。Linux 使用自己的真实外部路径，不复制 Mac 环境。长期证据应另选稳定存储。

新冻结计划使用独立的 schema_version=3，可保存研究定义 v1 或 v2，任务仍为普通 v3 实验。它保存模型/MDP/坐标副本、种子、协议、分析请求、资源和闭包；每个任务 origin/ 保留原文及 derivation.json，区分迁移与重复派生。复制后再次解析校验，执行不依赖原案例路径；安装态力场库在 build 时按 bundle 身份核验并冻结。修改冻结文件拒绝运行，不“修正哈希”继续。

旧版本 1/2 的冻结计划与批次保持只读，不改账本或用当前代码续跑。需要新执行时，从原研究源码创建新计划、新批次；历史实验/Run 的版本不因研究定义升级而改写。

## 批次、恢复与失败

输出为 `<output-root>/<plan_hash>/`，其内 `plan/`、`runs/`、`analyses/`、`events/` 及 `ledger.json` 形成一个可整体保存的批次。登记表只保存任务到 Run 的映射、操作事件和资源用量，真正状态读取普通 Run。所有任务的 Run 目标先独占登记，然后才启动构建。

```sh
materiasim research status /实际路径/批次目录
materiasim research run /实际路径/冻结计划 --output-root /实际路径/批次根 --resume
materiasim research compare /实际路径/批次目录
materiasim research compare /实际路径/批次目录 --output-root /实际路径/独立比较根
```

相同冻结计划在同一批次根重复提交只返回已有任务，不再生成四个 Run。`--resume` 只恢复可核查的中断或已完成交接；终止失败、缺证据、硬杀后的不确定状态均拒绝自动重建。显式换输出根会创建另一批次，不是全局去重服务。单写者锁依赖本机 POSIX 文件锁，不宣称集群全局锁。

首个失败即停，后续任务保持未启动并出现在 status/compare；不换种子、不删失败、不自动重分析。分析失败不会重开已完成的 MD；不完整或不可信证据不进入聚合。

## 资源限制

Research v2 的 limits 仅声明 max_tasks/concurrency/total_seconds/storage_bytes，线程、设备、构建/执行/分析预算和 attempt 上限来自每个实验的冻结 execution_profile v2/v3，不再维护第二套线程/GPU 配置。批次仍上限 1800 秒、1 GiB，不因单实验 profile v3 可表达较长任务而提高批次总额；当前双场景示例限定 4 任务。大规模/长时研究调度未交付。

整个子操作由同一个单实验监督器控制，覆盖 build/run/resume/analyze 的进程启动、Python 工作、原生工具和退出。控制账本位于 runs/.materiasim-operations/<RunID>/，与 manifest 绑定，分析不修改 MD Run。批次另监视总预算；其退出宽限为任务宽限再加 15 秒，避免外层先杀掉正在保存检查点的内层。预扣后记录实耗，未知交接保留预扣额度并拒绝继续。

新任务的单 Run 控制账本使用独立 contract_version=2：绑定请求/结果哈希、顺序和前次结算，核对有限非负计费、状态及实际事件目录；分析输出登记由操作请求逐项核查，不能删掉条目释放预算。冻结计划版本 3、研究定义 v2 和 execution_profile v2 不因此再次升级。

旧单 Run 控制账本 v1 只读，不原地补哈希或继续追加操作；已有 status/compare 证据可读取，新操作需匹配的源码快照或新的独立 Run。`archive` 可以导出某个完成态 Run、控制证据及登记分析，搬迁后用 `verify-archive` 核查；它不导出整个 Research 的计划、比较和批次账本，不支持批次活动路径迁移。完整研究备份仍须保留整批原始证据。任务退出后也检查资源阈值，退出码零不能覆盖超预算状态。

存储预检保守预留 64 MiB/任务，启动前要求有总存储预算对应的可用空间；执行时约每 0.1 秒检查目录字节和剩余磁盘。1 GiB 是停止阈值，不是硬配额：单次写入、检查耗时及停机宽限可能越过阈值。需要强隔离的正式生产应使用服务器配额/调度器，本轮未实现。

旧 Research v1 的显式操作上限和 20 秒外层宽限保留；默认 v2 实验迁移得到的 CPU profile v1 仍只有执行累计账本。新研究使用 profile v2 的全流程控制；不会悄悄把旧 Run 补成新契约。独立控制账本、Run、分析都需保留，复制 Run 单目录不能当成完整执行备份。GPU 候选逻辑和本机实际可用分开，未实测设备不会自动降级到 CPU。

## 比较与科学边界

比较逐项校验计划、Run、AnalysisRun 请求、原轨迹/坐标/映射、CSV 和报告哈希，再检查阶段、实际帧数/时间窗、截断、单位、归一化与分析实现身份。所有声明的重复和失败均保留，任何缺失不自动补零或剔除。

v2 decision_rules 包含 description 和有界 checks，支持 all_tasks_completed、analysis_valid、metric_range。范围规则必须引用已声明的 request_id/metric/unit 与明确 minimum/maximum；规则返回 pass/fail/not_assessed 及逐任务依据。它们仅是工程判据，不能授予 production 或 scientific pass。无分析的完整研究输出空 aggregates；分析失败、缺失或不可比的批次不整体聚合。

只有完整可比集合才输出各条件的运行均值的均值；不生成置信区间或独立样本数。ZIL 数量增加可能改变填水数与可接触分子对总数，原始计数不能直接解释为结合更强。两次 8 ps 工程重复不证明平衡、有效采样或模型科学适用性。
