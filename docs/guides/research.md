# 研究包使用指南

研究源码按 `studies/<id>/README.md`、`research.json`、`experiments/` 组织。它描述问题、对照、明确条件与重复，调用同一个模拟核心，不复制构建器或 runner。首个例子是 [zil_count_smoke](../../studies/zil_count_smoke/research.json)。

## 已实现范围

- `schema_version=1`，仅 `engineering_smoke`；至少两个显式条件，最多 16 个展开任务，串行 CPU。
- 当前重复展开接受 `packed_liquid`，且协议恰有一段生成初速度。预建结构仍可用普通单实验入口，不伪造其装填种子。
- 每个 case 对应完整实验配置；repeat 只允许 `id`、`packing_seed`、`velocity_seed`。继承速度阶段的 seed 保持 null；拒绝重复种子对、重复 ID、非法字段和隐式随机种子。
- 有意变化字段为 `component_counts`、`scenario`；模型/水模型、协议、阶段、选择、截断和其他未声明条件保持一致。首版不支持任意参数覆盖或跨力场、跨协议自动统计。
- 研究比较器只汇总已配置的 `component_contacts`；普通核心仍支持独立水化分析。观察量为 `mean_unique_molecule_pairs`，单位 `molecule_pairs`，没有按分子对总数归一化。

## 预检和冻结

以下命令使用已经安装本包的环境；从仓库根指定研究源码。预览不调用 Packmol/GROMACS，也不生成 Run。

```sh
materiasim research validate studies/zil_count_smoke/research.json
materiasim research plan studies/zil_count_smoke/research.json
```

保存必须显式指定一个尚不存在的仓库外目录：

```sh
materiasim research plan studies/zil_count_smoke/research.json --output /private/tmp/materiasim-study-plan
materiasim research run /private/tmp/materiasim-study-plan --output-root /private/tmp/materiasim-study-batches
```

路径只是示例，不能覆盖已有计划。当前输出校验拒绝符号链接组件；macOS 临时路径使用 `/private/tmp` 而不是 `/tmp`。Linux 使用自己的真实外部路径，不复制 Mac 环境。长期证据应另选稳定存储。

plan 保存全部任务的普通 v2 配置、原始模型/MDP/坐标副本、实际种子、协议、分析请求、来源文档哈希与闭包清单。复制后再次解析并校验，执行不依赖原案例路径；安装态 GROMACS 力场库仍在 build 时按 bundle 身份核验并冻结。修改冻结文件会拒绝运行，不“修正哈希”继续。

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

研究文件必须声明线程、任务/尝试数、构建/执行/分析秒数、累计预算和存储阈值。ZIL 示例限定 4 任务、2 线程、每 Run 最多 2 次执行尝试、执行每次 180 秒、构建 600 秒、分析 120 秒、累计 1800 秒、1 GiB。

整个子操作由外层监视，包括编译与分析；启动前先扣除授予预算和 20 秒退出宽限，交接成功后记实耗，崩溃后保守保留全额。所有启动共用累计预算，不因重新执行命令清零。核心子进程接到停止信号后最多再等 10 秒，然后杀掉其进程组。

存储预检保守预留 64 MiB/任务，启动前要求有总存储预算对应的可用空间；执行时约每 0.1 秒检查目录字节和剩余磁盘。1 GiB 是停止阈值，不是硬配额：单次写入、检查耗时及停机宽限可能越过阈值。需要强隔离的正式生产应使用服务器配额/调度器，本轮未实现。单实验 CLI 原墙钟参数语义不变；共用 CPU/GPU 资源格式留待 E 批。

## 比较与科学边界

比较逐项校验计划、Run、AnalysisRun 请求、原轨迹/坐标/映射、CSV 和报告哈希，再检查阶段、实际帧数/时间窗、截断、单位、归一化与分析实现身份。所有声明的重复和失败均保留，任何缺失不自动补零或剔除。

只有完整可比集合才输出各条件的运行均值的均值；不生成置信区间或独立样本数。ZIL 数量增加可能改变填水数与可接触分子对总数，原始计数不能直接解释为结合更强。两次 8 ps 工程重复不证明平衡、有效采样或模型科学适用性。
