---
type: validation-record
created: 2026-09-15
last_updated: 2026-09-15
scope: 架构方案 B—D、可安装核心、共享资产与研究包工程闭环
status: passed
scientific_quality: not_assessed
---

# B—D：可安装模拟包与研究包验收

对应[架构方案](../plans/2026-09-15__architecture__simulation-package-and-research-bundles__implementation-plan.md)。B—D 的当前受限子集通过 macOS CPU 工程验收；不代表 E—F、Linux/GPU、其他材料或科学验证完成。

## 实际交付

- 唯一执行核心迁入 `src/materiasim/`，命令为 `materiasim` / `python -m materiasim`。保留 v2 Run 格式，不维护旧包的第二套执行实现。
- 共享模型、相互作用包与协议迁入 `catalog/`；7 个根 examples 与旧配置的解析内容哈希一致。19 个源资产逐字节一致，19 个配置文档只调整必要引用。原案例/原 examples 保留，迁移关系在 [migration_map.json](../architecture/migration_map.json)。
- 研究包提供显式条件、种子重复、只读展开、闭包冻结、串行登记、累计操作预算、恢复检查和全部结果比较；研究层调用普通 build/execute/analyze，不复制科学引擎。
- 首个研究源码包为 [zil_count_smoke](../../studies/zil_count_smoke/README.md)。只接受当前 `packed_liquid` 重复展开与同协议组分接触比较，支持声明数量或场景变化，不支持任意参数覆盖、跨力场自动统计或置信区间。
- 手册归 `docs/guides/`，历史验收归 `docs/validation/`。历史事实/绝对 Run 路径保持原样，原目录保留指向新入口的说明；AGENTS 和两个项目技能的路由已同步。

## 安装与环境

复用 Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4。未使用 PowerShell，未改变模型、电荷、水模型、温压、约束或原 MDP 模板。

本轮用户继续授权后，仅在 `/private/tmp/materiasim-bcd.vZ6vBJ/build-env/` 安装构建工具 setuptools 80.9.0、wheel 0.48.0 及其依赖 packaging 26.3；没有修改原分析环境或全局环境。另建独立 wheel-env 安装本项目自身，无科学分析依赖。

- editable 安装后，从 `/private/tmp` 调用配置与研究校验通过，不依赖当前目录或隐式 PYTHONPATH。
- 最终 wheel：`verified-dist/materiasim-0.1.0-py3-none-any.whl`，SHA-256 `59ff5d4846056780206249dab7451be5b0d0143ee4e62e0470d5bd7cec48ffe1`。
- wheel-env 从仓库外完成研究校验以及真实无水 build/run。Run：`verified-wheel-runs/packed_zil_dry-311811f2c4584943813ab3e8676e2c8d`，EM＋NVT 完成。
- wheel-env 没有安装分析 extras，因此没有在该环境做 MDAnalysis 验收；四任务分析使用原已验证分析环境。安装态 GROMACS 力场库仍严格核对 bundle 哈希，不将整库打进 wheel。

## 测试与真实计算

最终 98 项 unittest 通过：保留全部原测试，新增资产/包边界、研究字段/种子/预算、冻结篡改、幂等登记、崩溃保守计费、防重复构建、文档链接及信号退出负例。`git diff --check` 通过。两套原案例和旧 examples 没有 Git 内容变化。

### 四任务研究包

最终批次：`final-batches/2c8f1ea430f39c9a785d5954aff81635cc616eec2e6296b36fab123d9524deb7`。

| 任务 | 实际组成 | Run ID |
|---|---|---|
| count_2 / r1 | ZIL 2、SOL 2941 | research-fad9aaff13424cde8381fe72e6c2b454 |
| count_2 / r2 | ZIL 2、SOL 2942 | research-b0a3dfe1d217496d92436f8d07049f84 |
| count_4 / r1 | ZIL 4、SOL 2925 | research-566eb899d1c84d5c8fa522d5d43ffe3c |
| count_4 / r2 | ZIL 4、SOL 2908 | research-08d191dae90d40c09ee68929d1c2dc44 |

每条均完成 EM、NVT 1000 步、NPT 1000 步、采样 2000 步，共 8 ps MD，CPU 2 线程、串行；每条分析 21 帧。最终累计操作实耗约 95.74 秒，批次磁盘用量约 82 MiB；没有超过示例的 30 分钟操作预算与 1 GiB 停止阈值。

独立最小镜像双循环对照四条轨迹的逐帧接触计数通过；再次提交同一计划不启动 worker，原批次文件字节保持不变。隔离副本篡改 CSV 或设置分析失败后，比较器保留四个条目、报告不完整并禁止聚合；正式批次未被修改。

实际水数随装填种子和数量变化，证明不能将本例称为固定水数/固定浓度对照。原始接触均值仅作工程输出，不根据两个短重复推断平衡、结合强弱或科学独立样本。

### 现有四场景回归

`final-scenario-regression/acceptance.json`：四例全部通过，耗时约 68.81 秒、磁盘约 76 MiB，科学依赖在前后审计中一致。

- ZIL×2＋水：8901 原子，独立计数 21 帧一致。
- CAT×2＋ANI×2＋水：8905 原子，21 帧一致。
- ZIL＋CAT＋ANI＋水：8897 原子，21 帧一致；NVT 640 步／1.28 ps 真实中断，随后原目标恢复完成。
- ZIL×2 无水周期盒：78 原子，11 帧一致；不代表固体或熔体。

### 批次信号恢复与保留失败

补测第一版把 GROMACS 收到 TERM 后的返回码 1 当一般失败；日志实际记录正常停止，现场保留于 `batch-resume/`，没有手改 failed 状态。

修复仅适用于动力学、确有外部中断、返回码恰为 1、原生 stderr 存在 TERM 标记的情况；仍调用原检查点/原子数/目标时间/完整输出/数值检查。普通非零退出、不匹配信号或错误检查点不放行。

最终补测 `batch-resume-verified/acceptance.json`：两个声明任务，首 Run `research-12c52394cd8247efbc69762f6bd3e4ad` 在 NVT 240/1000 步、0.48 ps 中断；显式 research run --resume 后在同一 Run 完成。事件顺序恰为 build → run → resume → analyze，没有重建或改种子；第二条正常完成。累计约 51.34 秒、42 MiB。信号修复后四任务与四场景已重新建立最终版本证据，较早批次未删除。

## 历史保护、预算口径与限制

实查旧 v1 `zil_smoke-cc049782b63a4f70a8560d5c24a6d0e6` 与 A 批 v2 `packed_mixture_water-6492c3936c804cc6a5a855b891922bd6`：新入口可只读完整性校验，前后文件清单/字节未变；分别因只读格式、旧源码身份拒绝新执行。没有加入 force 绕过。

累计预算涵盖每次 worker 的构建、编译、运行、分析及退出宽限；交接崩溃保守保留预扣额度。存储每任务先按 64 MiB 做准入预留，再运行中巡检；1 GiB 是停止阈值而非操作系统硬配额，写入和退出宽限可能超过阈值。登记锁是单物理目录 POSIX 锁，不是远程全局调度器。

技能 quick_validate.py 因原环境缺少 PyYAML 未运行成功；没有为此新增依赖。已用项目测试检查两个技能的原 name/description、有效文档路由，并人工复核授权边界。simulation-research 使本轮显式保留失败/重复及工程与科学结论的区别；skill-creator 仅用于窄范围路由和已实现流程更新。

Linux、GPU、Slurm、硬磁盘配额、灾难恢复、跨版本继续旧 Run、正式长轨迹，以及混合溶剂、聚合物、固相和纳米材料均未验收或未实现，不能外推为完成。E—F 仍未实施。

## 证据与复查入口

工程证据根：`/private/tmp/materiasim-bcd.vZ6vBJ/`，是可能被系统清理的临时目录，不是长期科研归档，也未提交 Git。

- 最终研究独立审计与拒绝负例：`final-research-audit/acceptance.json`。
- 最终比较：`final-comparisons/comparison-8c4ea73bad444092b635e2cb3c955709/report.json`。
- 场景审计：`final-scenario-regression/acceptance.json`；信号恢复：`batch-resume-verified/acceptance.json`。
- 每个 Run/AnalysisRun 保存自身输入、实现、工具、状态与产物哈希；没有用本文替代原始证据。

从仓库根使用原分析解释器：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -v
```

真实验收工具为 `tests.acceptance.verify_architecture_a`、`tests.acceptance.verify_research`、`tests.acceptance.verify_research_resume`，通过 `python -m` 调用，参数见 --help；后者和场景验收会启动小量 MD，必须指定新的外部输出。没有自动 commit 或 push，原备份提交 `9aae83d` 保留。
