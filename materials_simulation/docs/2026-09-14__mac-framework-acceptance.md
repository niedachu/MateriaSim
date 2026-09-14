# 第一轮框架：Mac CPU 工程验收

日期：2026-09-14。范围：升级方案 P0 基线检查与 P1a 最小闭环，不是整个多材料平台验收。

结论：最终代码在 macOS 上完成 ZIL 水盒构建、能量最小化、短动力学、真实检查点中断/续跑及新旧分析对照。Linux 未实测。短程轨迹没有建立平衡或科学模型的新验证结论。

## 交付与边界

- 新增 `materials_sim/` 的 12 个职责模块、两个 JSON 示例、22 项单元测试，以及两个可复用验收工具；实际入口见 [README](../README.md)。
- 本轮未安装软件、创建 Python 环境、改依赖或使用 PowerShell；未改动 ML、原始拓扑/MDP、旧 runner、历史科研输出，也未进行 Git 写操作或旧文件清理。
- 模型卡复用 GAFF2/AM1-BCC ZIL，使用本机 GROMACS 中的 Amber14SB/TIP3P 相关文件并完整快照。物理参数不自动替换，派生变化仅为工程步数、显式种子及输出频率。
- 输入拓扑/MDP 的七项源哈希与模型卡一致；历史 `ACCEPTED.json` 中五个拓扑/构象哈希仍全部一致。这不等于重新验收历史 Windows 科学结果。

## 环境与规模

| 项目 | 实测 |
|---|---|
| 平台 | macOS、Apple Silicon、原生 CPU |
| Python | 3.9.25，复用既有 ZIL 分析环境 |
| GROMACS | 2026.3-Homebrew；1 个 thread-MPI rank、2 个 OpenMP 线程 |
| 分析 | MDAnalysis 2.7.0、NumPy 1.26.4 |
| 组成 | ZIL 1 个、TIP3P 水 2,957 个，总原子 8,910 |
| 初始盒子 | 4.5 × 4.5 × 4.5 nm，正交周期盒 |
| 总电荷 | 约 0.000017 e，来自既有序列化电荷精度 |
| 协议 | EM ≤5,000 步；NVT 1,000、NPT 1,000、采样 2,000 步；dt=0.002 ps |
| 预算 | EM 验收调用 120 秒；中断测试 2 秒；完成续跑 180 秒；均未扩大为长程生产 |

## 最终 Run

标识：`zil_smoke-cc049782b63a4f70a8560d5c24a6d0e6`。

- [完整工程 Run](</private/tmp/materials-framework.gXhzaZ/最终 异地验收/zil_smoke-cc049782b63a4f70a8560d5c24a6d0e6>)
- [结构化验收摘要](</private/tmp/materials-framework.gXhzaZ/final-evidence/acceptance.json>)、[单元测试日志](</private/tmp/materials-framework.gXhzaZ/final-evidence/framework_tests.log>)
- [旧核心测试日志](</private/tmp/materials-framework.gXhzaZ/final-evidence/legacy_tests.log>)、[新旧逐帧对照](</private/tmp/materials-framework.gXhzaZ/final-legacy-comparison/comparison.json>)
- [输入/检查点/轨迹变更拒绝证据](</private/tmp/materials-framework.gXhzaZ/final-mutation-fixtures/guard_results.json>)
- [新水化分析报告](</private/tmp/materials-framework.gXhzaZ/最终 异地验收/zil_smoke-cc049782b63a4f70a8560d5c24a6d0e6/analysis/7fde2e09492e492fa2dcf229511f9768/report.json>)

以上原始工程证据位于 `/private/tmp`，本轮未删除，但可能被系统或后续清理移除；它们不是正式科研归档。本文保留验收摘要，若需要长期保留全部轨迹/日志，应另行指定稳定存储位置，不能把只有本文视为完整复现包。

实验内容哈希：`2fb6e7daad6444b46991da7b0ecc90e21fafd75549cf1fed3f6fe1c5ca72fc39`。实现文件与实际引擎二进制哈希均在 Run manifest 和验收 JSON 中。

## 验收结果

| 检查 | 实际结果 |
|---|---|
| 新框架单元测试 | 22 项通过：配置、哈希、路径、锁、原子顺序、协议派生、异常结果、残留输出、周期距离和去重 |
| 旧水化核心测试 | 5 项通过 |
| 构建 | 原生 editconf/solvate/grompp 通过；无 maxwarn 绕过；原子映射、组分、盒子和净电荷检查通过 |
| EM | 第 909 步达到 Fmax <500 kJ mol⁻¹ nm⁻¹ |
| 真实中断 | NVT 在第 640/1000 步、1.28 ps 写出检查点；被识别为可恢复而非完成 |
| 真实续跑 | 使用相同 TPR、`-cpi/-append` 到 NVT 1000 步；NPT 1000 步、采样 2000 步均完成 |
| 输出验证 | 实际检查点时间分别为 2、2、4 ps，原子数均 8,910；日志/坐标/轨迹/能量/检查点通过检查 |
| 输入改变 | 隔离副本改动输入、检查点或轨迹后均拒绝恢复，未创建新执行 attempt |
| 状态保护 | 中断 Run 不能用 run 重启；完成 Run 不能 run/resume 重开；残留输出拒绝覆盖；锁冲突回归通过 |
| 输入隔离 | 独立 macOS 沙箱进程禁止读取旧 topology/ 和 mdp/；先确认 ls 被拒绝，再成功执行最终续跑及剩余阶段编译 |
| 路径 | 新建 Run 从原位置移动至另一中文/空格路径，从 `/private/tmp` 工作目录调用，成功续跑/分析；旧案例未移动 |
| 只读命令 | doctor/validate/status/report 前后所有 Run 文件字节哈希相同，无隐式 MD |
| 分析对照 | 同一采样轨迹的 21 帧、三个分位点和总去重计数，新旧分析逐帧完全一致；时间也一致 |
| 原输入保护 | 五项历史接受哈希、七项模型输入校验全部通过 |

动力学时间在各阶段内从零计数，2+2+4 ps 为总积分长度；不能把采样段 4 ps 误写成 4 ns。续跑输出帧由 GROMACS append 校验，分析拒绝非单调/重复时间。

## 基础数值诊断，不是平衡证据

从最终采样段 EDR 使用原生 `gmx energy` 读取 21 个输出点；命令和 XVG 在 `final-evidence/` 中。

| 量 | 输出点平均值 | 首点 → 末点 |
|---|---:|---:|
| 势能 / kJ mol⁻¹ | -121552.656 | -123354.547 → -120150.094 |
| 温度 / K | 281.001 | 273.957 → 286.351 |
| 密度 / kg m⁻³ | 996.226 | 984.100 → 998.879 |

温度仍低于 298 K 目标且有漂移，这正说明短程测试不能用于宣称已平衡。这里仅验证可解析且有限的数值输出；不提供收敛结论、独立样本数或置信区间。

水化分析采用临时 0.35 nm 接触阈值，未去除平衡段。输出的标准差是这些相关帧的总体描述标准差，不是均值不确定度；`scientific_quality` 明确为 `not_assessed`。

## 开发期失败与修复记录

按 `simulation-diagnostics` 保留现场，未手改失败 Run 为成功，也未以换物理参数或删断点解决问题。

1. `zil_smoke-a025ca62e4cd477f9ab4b30820d67d2c`：EM 已收敛，初版检查器把合法输入 `epsilon-rf = inf` 误判为数值失败。修复为只允许这一明确输入约定，真实非有限结果和 LINCS 警告仍失败；已补回归。
2. `zil_smoke-e9de30742e464de7ad2cd2b2f31b3979`：真实 maxh 中断生成检查点但不写最终 GRO，初版误要求最终坐标。修复为完成态要求 GRO、中断态校验检查点；已补回归。
3. `zil_smoke-2673513bb0ca402499b768eb275dd820`：修复后完整闭环通过。随后补上完成边界的停止信号处理与残留输出测试，使用上面的最终 Run 再验收，未改写这条开发期 Run 的实现身份。

前两条位于工程临时根的 `工程验收 runs/`，第三条位于 `异地 续跑/`。最终证据不把失败尝试算成成功，也不把开发期尝试当作独立科学重复。

## 未验收和未实施

- Linux、GPU、Slurm、多机及集群文件系统锁：未实测；本轮没有相应设备/环境。
- 硬杀/断电恢复、磁盘不足、父 Run 派生、源码或引擎升级后的历史 Run 兼容：未实现自动处理，失败/不确定状态须诊断，不手改解锁。
- CAT/ANI 公共核心复用、多溶质装填、聚合物链、纳米颗粒、混合界面、LAMMPS/粗粒化、参数化与 GUI：尚未实施。
- 正式长程采样、独立重复、科学模型跨平台一致性及物性验证：未做。
- 未建立 Git 仓库、迁移旧项目、清理旧环境、制作发行包或安装新依赖。

下一步应先做 P1b 的 CAT/ANI 共用核心与 Linux 同流程验收，再决定首个聚合物模型；不能把本轮小分子工程验收外推为任意多组分体系可用。
