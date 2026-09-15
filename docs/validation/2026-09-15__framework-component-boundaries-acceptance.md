---
type: validation-record
created: 2026-09-15
last_updated: 2026-09-15
status: passed
scope: P0 基线及 P1/P2 组件边界子批；不代表 P1/P2 整体完成
scientific_quality: not_assessed
---

# 可扩展框架：组件边界子批验收

对应[框架第一版方案](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)。

结论：本子批通过 macOS CPU 工程验收。P0 完成；P1/P2 的统一校验、组件适配、能力查询与错误/分析契约已落地。Experiment/Run v3、Research v2、完整模型/协议中间表示、ExecutionProfile 和分层运行身份均尚未完成，不能称为 P0—P2 全部完成。

## 1. 备份与改动边界

用户要求先 commit 备份再实施。已创建本地提交：

`e223731 Preserve validated package and research baseline before extensible framework work`

提交包含此前 A—D 的源码/资产迁移、研究源码、文档和新方案；没有 push。提交前重新运行 98 项测试通过。对 247 个候选文件做常见敏感文件名、密钥模式和异常体积检查，未发现命中；该检查不是完整安全审计。

提交的空白检查曾报告 4 个冻结 MDP 与方案末尾空行。MDP 保持与原模型资产逐字节相同，未为消除提示改写。备份提交不包含 Git 忽略的环境、轨迹和历史科学输出，不能替代完整数据备份。

本子批新增改动仍留在工作树，未再次提交。catalog、examples、studies、两个历史案例和 pyproject.toml 无本轮内容修改；没有安装新依赖、改力场、电荷、水模型、原协议模板或全局环境，没有 PowerShell。

## 2. 实际实现

- 完整配置入口归入 `workflows.validation.load_spec`；`specs.schema.read_spec` 只解析格式/资产。项目内调用与测试导入同步迁移。
- specs 不再导入 GROMACS、具体场景或分析算法。实际适用性由统一入口调用已登记组件检查，MDP、装填、无水水化等拒绝规则保留。
- 已有 GROMACS 通过 EngineAdapter 提供静态校验、环境查询、构建和阶段执行；共用 build/execute 消费 BuildResult、StageEvidence，不复制 runner。
- 构建结果发布前核对持久化映射、实际组成、引擎和产物哈希，不用返回值覆盖实际文件事实。
- 场景和分析登记描述由 capabilities 同源读取；静态查询不启动工具，环境明确 not_checked。
- 两类接触分析使用角色/格式化输入；只打开独立 AnalysisRun 内的副本。报告增加 result_contract，保留原 CSV、算法数值及科学未评估状态。
- CLI 参数错误和主要边界错误通过 stderr JSON 输出。未细分旧错误仍为 INVALID_SPEC/OPERATION_FAILED，不冒充完整错误分类系统。
- 研究重复展开改为调用统一配置校验；原 Research v1 受限表达、总预算和失败保留不变。

本轮只对已有能力做接口改造。没有空后端、假聚合物构建器、动态插件脚本、GPU 执行、服务器调度或新的科学观察量算法。

## 3. 测试与真实环境

复用 Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4。

从仓库根运行：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -v
```

最终 **112 项测试通过**：原 98 项加 14 项组件边界测试。新增测试覆盖纯规格依赖方向、能力与真实登记一致、替换引擎/场景/分析的实际调用、私有分析输入、构建交接、格式拒绝、结构化参数/资源/依赖错误等。测试替身只存在于测试，不登记为产品能力。

本轮差异 `git diff --check` 通过；文档引用与技能边界测试通过。8 个真实 Run 随后独立调用 verify_run，确认全部完成、冻结输入/产物有效且源码身份仍与本轮一致。

## 4. 真实 CPU 验收

证据根：[framework-boundaries-20260915-01](/Users/niezhidong/Desktop/MateriaSim-runs/framework-boundaries-20260915-01)。

入口为 `tests.acceptance.verify_component_boundaries`，显式 --output；该命令会启动小量 MD，不是只读查询。真实任务为 4 个装填示例、2 个预建示例及恢复研究中的 2 个任务，合计 8 个 Run。

使用 CPU 2 线程、串行、现有短协议；单实验执行墙钟参数 180 秒，整批 30 分钟、存储停止阈值 1 GiB。实际约 **157.63 秒、160,645,753 字节（约 153 MiB）**。存储值为报告写入前计数，阈值与逐操作检查不是操作系统硬配额。

| 示例 | 实际组分 | 分析对照 |
|---|---|---|
| packed_zil_water | ZIL 2、SOL 2941 | 21 帧，独立最小镜像分子对计数一致 |
| packed_ions_water | CAT 2、ANI 2、SOL 2941 | 21 帧，独立计数一致 |
| packed_mixture_water | ZIL 1、CAT 1、ANI 1、SOL 2939 | 21 帧，独立计数一致 |
| packed_zil_dry | ZIL 2，无水 | 11 帧，独立计数一致；不是固体 |
| zil_smoke_v2 | ZIL 1、SOL 2957 | 21 帧，与保留案例水化算法逐帧一致 |
| cat_ani_smoke | CAT 1、ANI 1、SOL 2957 | 21 帧，与保留案例水化算法逐帧一致 |

6 个单实验的分析前后源 Run 全部文件哈希不变；依赖清单在验收前后相同。预建水盒重新加水仍不保证跨次字节一致，本轮比较的是同一冻结轨迹上的分析，不声称修复了历史随机删水问题。

恢复研究：首任务在 NVT **240/1000 步、0.48 ps** 收到 TERM 后保留检查点，以同一 Run 恢复原目标；第二任务正常完成。事件顺序为 build → run → resume → analyze，未重复构建。该子批累计计费约 46.01 秒。

## 5. 证据入口

相对于上述外部证据根：

- `acceptance.json`：总状态、实际源码/工具身份、全部任务引用、预算与限制。
- `unit.stderr`、`unit.stdout`：112 项测试输出。
- `dependencies_before.json`、`dependencies_after.json`：输入与间接库身份。
- `runs/`：6 个单实验的原始运行证据。
- `checks/`：分析副本、独立计数及原案例算法对照。
- `research_resume/acceptance.json`：两个任务的真实中断恢复证据。
- `research_resume/batches/`：冻结计划、Run/AnalysisRun、账本与失败/恢复事件。

这些是仓库外的新工程证据，没有移入 Git，也没有自动建立异地备份。旧 /private/tmp 验收结果和原始资料均未迁移或删除。

## 6. 未完成与已发现的限制

- v3 格式和显式迁移未实现，新建 Run 仍使用 v2；继续运行仍检查整个 Python 包身份。
- 协议仍含当前 GROMACS MDP 与短测语义，构建步骤未完全提升为引擎无关规划，PreparedStage 契约未完成。
- Research v2、不同场景/指标的通用研究比较、统一 CPU/GPU profile、长任务用途准入、分层身份与大轨迹存储未实现。
- 当前分析器仍全部需要原子映射，结果封装不是任意物性协议或统计质量验证。
- 本轮从源码运行，没有重做发行包安装验收。检查确认：复用的分析解释器在仓库外、移除 PYTHONPATH 后运行 `python -m materiasim` 会报 No module named materiasim；它并未安装本项目。源码入口按既有指南可用，没有为消除此提示自动安装包。此前隔离 wheel 环境的安装验收属于旧记录，不能替代本轮。
- Linux、GPU、长期负载、混合溶剂、聚合物、固相、纳米材料和科学验证均未完成。
- 导入迁移时首次机械补丁格式错误导致 7 个测试模块导入失败；修正调用方迁移后，保留所有原断言重新运行通过。未通过跳过测试或兼容回退掩盖该开发失败。
- simulation-research 技能使本轮保持有限短测、原始输入不变、失败与未验收项可见、工程/科学结论分开。

下一步应完成 P1 的版本化模型/协议契约与迁移，并让研究冻结计划、Run 记录及恢复检查一起适配；不能把本子批称为整份方案或 P0—P2 已全部完成。
