# 通用研究与全流程资源：Mac CPU 工程验收

日期：2026-09-15。状态：本批工程验收通过；P4 尚有用途/非短测收口，整份方案未完成；科学质量未评估。

对应[框架方案第 18 节](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)。用户授权继续实施及小量验收；无新依赖安装、原模型/MDP 改写、commit 或 push。原备份提交 e223731 不变，当前改动仍在工作树。

## 交付与范围

- Research v2 的真实场景种子槽、双分析/无分析、显式差异和结构化工程判据。
- 分析方法提供指标/单位/归一化和结果文件；研究调度不再只接受 packed_liquid 与 component_contacts。
- 新冻结计划版本 3，兼容读取旧计划 1/2；原研究定义 1 保留窄范围，新任务使用独立原文/种子派生记录。
- execution_profile v2、独立全流程账本和同一个 build/run/resume/analyze 监督器；控制身份与 Run 绑定，分析不写 MD Run。
- 单 CUDA GPU 候选配置、设备/构建查询、显式非键/PME 参数及当次原生报告核查；GPU bonded/update、其他 GPU 后端没有实现，不声称硬件验收。

P4 的正式用途审批、非短测开放，以及 P5/P6 的完整存储/灾难恢复与安装交付仍待完成。原工程步数、科学参数、模型来源和算法数值定义没有放宽。

## 单元与静态验证

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m unittest discover -s tests -q
```

基线 143 项，增加 21 项，最终 164 项通过。新测试覆盖双场景/双分析、预建无装填种子、缺槽/额外槽/重复种子、无观察量、未知单位/方法/判据、物理与资源比较分开；CPU/GPU 配置、设备未知/禁用、UUID 可见性、卸载日志缺证据/错误映射、累计操作计费、崩溃预扣、账本重置和磁盘拒绝。

GPU 测试使用明确的合成驱动/日志夹具，只验证逻辑，不伪造实际 GPU Run。原生候选配置 `examples/v3/packed_zil_water_gpu.json` 的 validate 通过；这不代表当前设备可执行。`studies/mixed_builders_smoke/research.json` 的只读 validate 展开 4 个任务。

## 真实入口、预算与环境

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_research_v2 \
  --output /Users/niezhidong/Desktop/MateriaSim-runs/research-execution-20260915-01
```

此命令启动小量 MD：14 任务、CPU 2 线程、串行；沿用 EM 最多 5,000 步、动力学每阶段最多 2,000 步；整批上限 1800 秒、输出停止阈值 1 GiB。复用 Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4。

结果 status=passed、pending=[]；**313.77 秒，293,011,022 字节（279.44 MiB）**。字节数在最终总报告写入前采样；不是文件系统硬配额。源码在整批前后哈希一致。

8 个既有回归任务覆盖四种装填例、两个预建例及两任务研究恢复；四个装填例继续用独立最小镜像算法，两个预建例用原水化算法对照。具体 ID 和原生准备证据保存在 `existing/acceptance.json`，不拿历史记录代替当次运行。

新增 profile v2 的六个 Run：

| 任务 | Run ID | 全流程控制事件 | 计费秒数 |
|---|---|---|---:|
| 预建重复 1 | research-cf120ec398c34c30a36f5674142905bd | build/run/resume/analyze | 24.317 |
| 预建重复 2 | research-8eeba8a5c8e845a28a47b20caa9e1db6 | build/run/analyze | 22.866 |
| 装填重复 1 | research-b39b077d58a94a4bb111359197fea2e4 | build/run/analyze | 23.608 |
| 装填重复 2 | research-e582c43961094fcb82dd4ae7627643d8 | build/run/analyze | 23.800 |
| 无分析预建 | research-14defd8effcd40f7ac4be6044ad29892 | build/run | 21.540 |
| 无分析装填 | research-adad18e04780428c869a100e76065240 | build/run | 22.812 |

共 14 个 Run、54 个阶段，各阶段恰好一次成功原生编译。新四任务研究的首个 NVT 在 **240/1000 步、0.48 ps、8,912 原子**时受控 SIGTERM 中断；多层监督正确传递停止，保留有效检查点并恢复同一 Run，没有重建体系、重编译或替换目标。

每个场景的两个重复和两种分析全部保留，工程检查均 pass。两组水氧并集均值约 17.476 与 35.786，原始分子对均值均 0；场景和组分数量同时变化，不能把这些原始计数解释为水化更强、结合能力或平衡占有率。没有自相关校正、独立样本数或置信区间。无分析研究为 engineering_complete、aggregates=[]，没有分析目录。

## 完整性与历史核查

- profile v2 六个 Run 的当前执行身份、准备记录和绑定控制账本通过，所有操作事件闭合，分析被计入全流程账本而非写回 MD Run。
- 六个既有示例与上一批 v3 契约验收相比，冻结 inputs、派生 MDP、protocol_overrides.json 逐字节相同。动态轨迹不要求逐位一致；旧预建 CAT/ANI 的 solvate 随机删水限制保持。
- 上一批 `v3-contracts-20260915-01` 的 8 个 Run、2 个旧冻结计划可只读核查；1,382 个文件在审计前后不变。跨源码执行全部按 Implementation changed 拒绝，没有新 attempt 或补写记录。
- 没有物理参数调整、maxwarn 放宽、删失败、删断言或安装替代引擎。

## GPU 核查依据与未验收范围

本机 doctor 实测：GPU support=disabled、MPI library=thread_mpi；nvidia-smi 缺失，所以设备查询为 unknown，不是 GPU 可用。GPU 仅完成配置、参数和拒绝测试，未启动 GPU MD。

原生参数与检查点语义核对 [GROMACS mdrun 文档](https://manual.gromacs.org/documentation/current/onlinehelp/gmx-mdrun.html)和[性能指南](https://manual.gromacs.org/documentation/current/user-guide/mdrun-performance.html)；设备清单核对 [NVIDIA 文档](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。日志识别参考 GROMACS 项目实际 [PP/PME 启动报告](https://gitlab.com/gromacs/gromacs/-/issues/5013)，仅接受当前明确的单设备映射，未知格式拒绝。

未完成：用途审批与非短程策略、完整复制前容量和封存预算、共享输出隔离、控制/分析路径迁移、强杀进程树及损坏账本边界、安装态/发行包和完整 agent 工具验收。Linux/GPU 真实运行、长负载、科学收敛和新材料全部未验收。

## 证据位置

根目录：`/Users/niezhidong/Desktop/MateriaSim-runs/research-execution-20260915-01/`。

- acceptance.json：当次源码身份、14 任务总结果、资源记录和逐阶段审计。
- existing/：8 个既有回归任务、164 项测试日志、独立算法对照。
- mixed_recovery/：四任务计划/批次、中断封存、双分析比较及每 Run 独立控制账本。
- no_analysis/：两任务无分析研究和空观察量结果。
- Run 同级 .materiasim-operations/：请求、标准输出/错误、结果、结算、控制身份；不是可删缓存。

依据 [simulation-research 技能](../../skills/simulation-research/SKILL.md)执行有界短测、独立输出、来源与失败保留，严格分开工程通过和科学证据。原始验收目录不手改，也不将此摘要当作完整科研数据备份。
