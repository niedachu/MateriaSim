# v3 契约与迁移：Mac CPU 工程验收

日期：2026-09-15。状态：本子批通过；整份框架方案尚未完成；科学质量未评估。

对应[可扩展框架方案](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)第 17 节。用户授权继续实施与既有小量验收；原备份为 e223731，本轮未 commit/push，未安装或升级依赖。

## 实际交付

- v3 实验的组分/模型、来源/分辨率、带格式资产、相互作用包、盒向量/边界、构建器、物理协议、输出要求和 CPU 执行配置。模板仍是原生有效输入来源，显式物理声明与模板冲突拒绝。
- v2 输入确定性转换为唯一新执行格式 v3；只读 migrate 预览；原生 v3 示例；新 Run 冻结原文、源/目标解析身份及转换报告。缺失模型来源不推断，不重写历史 Run。
- 真实预建与 Packmol 构建器登记、BuildPlan 消费和落盘；初版一项原生流水线，初始预处理服务于映射校验，不是任意 DAG。
- 操作源码闭包及物理/构建/执行/资源/分析身份分离；执行依赖包含函数内导入和传递依赖。整体源码身份仍作为诊断，不能通过删除执行依赖校验恢复。
- 有界 CPU 配置由执行器消费，跨 attempt 预算预留/实耗计费；重置账本、未闭合交接和超额拒绝。build/analysis 尚不属于单 Run 这份总额，研究外层仍另行计费。
- 研究源码格式仍 v1；新冻结计划版本 2、任务版本 3，保存原文及种子派生来源。旧计划只读，现有 packed/组分接触研究范围不扩大。

原模型、力场、电荷、水模型、温压、步长、原始协议模板和原分析数值定义未改变。此处 v3 是表示与执行契约升级，不是新材料或科学用途批准。

## 测试与问题记录

从仓库根使用现有解释器：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m unittest discover -s tests -q
```

基线 124 项；最终 143 项通过。新增覆盖六例迁移、资产搬移后身份、来源保留、物理声明/模板冲突、未实现设备/边界/构建器/分辨率、精确模型覆盖、文件格式、CLI 非法输入、物理/资源/分析身份分离、源码依赖递归、预算累计/重置/未知交接、研究资源冲突、缺准备记录和来源篡改等。

第一轮全测有 3 项错误、1 项失败：旧执行替身未提供新冻结配置、研究种子断言仍访问旧字段、旧 v2 恢复断言仍预期全源码变化错误。按确定的新格式和旧 Run 只读策略迁移夹具/断言后通过；没有删除恢复拒绝或预算检查，也没有伪造原生模拟成功。

原生 v3 示例 `examples/v3/packed_zil_water.json` 的 CLI validate 通过，解析身份为 `5ee125452aff57c082a0e60933a65fcc56320cc699b1589ce5d4dad6e6d672dd`。同一契约还由下述研究快照的真实 v3 输入构建验证，不止静态解析。

## 真实运行、预算与环境

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_component_boundaries \
  --output /Users/niezhidong/Desktop/MateriaSim-runs/v3-contracts-20260915-01
```

该命令会启动小量 MD。复用 macOS Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4。未使用 PowerShell；没有改变环境。

CPU 2 线程、串行；单次执行 180 秒，现有 EM 上限 5,000 步、动力学每段不超过 2,000 步；整批含构建/分析上限 30 分钟，输出停止阈值 1 GiB，不是 OS 硬配额。完成结果 status=passed、pending=[]，约 **164.23 秒、161,448,602 字节（153.97 MiB）**。大小是最终总报告写入前的采样值；依赖与源码身份在验收期间保持不变。

| 实验 | 实际 Run ID | 验证 |
|---|---|---|
| packed_zil_water | packed_zil_water-32410c02081c4b7099e4a4bb52c9dc88 | 两个 ZIL 实例与填水、4 阶段、独立接触计数 |
| packed_ions_water | packed_ions_water-a50677fd32954572a56213046f4da2c9 | CAT/ANI 多副本与填水、4 阶段、独立接触计数 |
| packed_mixture_water | packed_mixture_water-2d738bc3423648d09d664f008d80695b | 三组分加水、4 阶段、独立接触计数 |
| packed_zil_dry | packed_zil_dry-36a337c6b85f4d928efba2d645402048 | 无水周期盒、2 阶段；不是固体验收 |
| zil_smoke_v2 | zil_smoke_v2-2922481bd9aa49819e76ddb145072cb0 | v2 源配置→v3 Run，预建水盒与原水化算法对照 |
| cat_ani_smoke | cat_ani_smoke-162eaffa03eb4af4b0f499daf7107a95 | 预建离子对水盒、原水化算法对照 |
| 研究 count_2 | research-a35aff4bd65940a88e1d0542eec36267 | v3 冻结任务、4 阶段、同 Run 中断恢复 |
| 研究 count_4 | research-dea533d156654e789293914587735a14 | v3 冻结任务、4 阶段、批次比较 |

共 **8 个 v3 Run、30 个阶段**。全部阶段恰好一次原生编译，逐项检查准备契约、输入闭包与产物。研究 count_2 的 NVT 在 240/1000 步、0.48 ps、8,901 原子时真实中断，然后以同一个 Run、原 TPR 和原准备记录使用 `-cpi/-append` 恢复到目标；没有重复构建或重新编译。

四个 packed 示例的逐帧接触与独立最小镜像算法一致；两个预建示例与原水化算法一致。分析前后源 Run 不变。研究比较为 engineering_complete，但每个条件仅一次，不是独立重复或科学统计验收。

## 额外只读审计

验收结束后逐个执行当前 `verify_run` / `verify_execution`：8 个新 Run 通过，manifest 均为版本 3、与当前执行闭包一致。六例来源报告 source_schema=2，两研究 Run 的直接冻结输入为 source_schema=3，研究 origin 继续保存更早源文档。

8 份 execution.json 均 active=null、所有事件闭合。恢复 Run 有 2 次执行 attempt，其余各 1 次；恢复 Run 累计执行实耗约 22.044 秒，另一研究 Run 约 22.271 秒。外层批次另记约 47.223 秒，因计费范围不同，不将两层费用简单相加。

上一批 `prepared-stages-20260915-01` 的 8 个 v2 Run 与旧冻结计划通过只读验证；1,319 个文件在检查前后哈希不变。当前 verify_execution 全部明确拒绝 `v2 is read-only`，未生成 attempt 或回填新字段。

六个相同示例与上一批逐项核对：冻结 inputs、build 中派生 MDP、protocol_overrides.json 全部逐字节相同。resolved_spec 的 JSON 身份因格式升级改变；不以此宣称物理改变，也不要求动态轨迹逐位一致。旧 CAT/ANI `solvate -maxsol` 的随机删水限制保持原记录，不承诺重建坐标确定性。

## 证据位置与边界

完整证据根：`/Users/niezhidong/Desktop/MateriaSim-runs/v3-contracts-20260915-01/`。

- `acceptance.json`：整批结果、工具/源码身份、六例审计与研究恢复、预算和大小。
- `unit.stderr` / `unit.stdout`：验收启动前 143 项测试。
- `runs/`、`checks/`：六例真实 Run、独立分析及算法对照。
- `research_resume/interruption.json`、`research_resume/acceptance.json`：实际中断、恢复与批次比较。
- 每个 Run 的 `manifest.json`、`provenance/`、`build/plan.json`、`execution.json`、`stages/*/stage.json` 和 `attempts/`：契约、来源、资源实耗、实际编译/执行命令。

尚未完成：通用 Research v2、多场景种子策略与多方法比较；完整 CPU/GPU ExecutionProfile、用途策略和全链路预算；完整存储/容量保护及 agent 失败路径；安装态/发行包及仓库外调用验收。当前从源码运行，未安装本项目到复用解释器。

Linux/GPU、长负载、新材料和科学收敛未验收。依据 [simulation-research 技能](../../skills/simulation-research/SKILL.md)落实了短测预算、独立输出、输入身份和工程/科学证据分离；这些工程通过不能作为任意多组分多场景或物性可信的证明。
