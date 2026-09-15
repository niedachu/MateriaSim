---
type: validation-record
created: 2026-09-15
last_updated: 2026-09-15
scope: 架构方案 A 批职责拆分、资产身份与 macOS CPU 短程回归
status: passed
scientific_quality: not_assessed
---

# 架构 A 批：职责拆分验收

本记录对应[架构实施方案](../plans/2026-09-15__architecture__simulation-package-and-research-bundles__implementation-plan.md)的 A 批，不代表可安装包、研究包、GPU 或新材料支持已经完成。

## 备份与改动边界

开始改动前按用户要求创建本地提交 `9aae83d`，包含当时源码与三份方案文档；未推送。被 Git 忽略的环境、轨迹和历史输出不属于 Git 提交备份。

本批实现：

- 通用 POSIX 子进程移至 `materials_sim/runtime/process.py`。GROMACS 保留冻结 GMXLIB 的专属薄封装；Packmol 不再调用 GROMACS 封装。
- `protocol.py` 校验阶段顺序、目标和状态交接；`engines/gromacs/mdp.py` 负责 MDP 内容、协议绑定和派生。
- 原 `assembly.py` 的职责分别归入 `builders/regions.py`、`scenarios/packed.py` 与 `engines/gromacs/parameters.py`；旧源码文件已被职责拆分替代，不保留第二套实现，可从备份提交查看。
- GRO 写出归 `engines/gromacs/coordinates.py`；显式组成和分析请求归 `specs/`，分析调度不再依赖 v2 配置解析器。
- 更新真实调用方与测试导入，没有改变旧测试的科学断言。

没有改动两套案例资产、现有实验示例、MDP 原模板、相互作用包或历史结果；没有新增依赖、移动虚拟环境、改变 Run 格式、放松科学限制或修改 CPU/GPU 运行参数。

## 静态与单元验证

改动前 66 项测试通过；改动后 78 项测试通过。新增 12 项覆盖：通用进程无 GROMACS 环境注入、引擎专属冻结路径、实际 stdin/参数/日志、非零退出、重复记录拒绝、超时和信号处理恢复、独立区域/阶段契约、GRO 顺序与单位、依赖方向及嵌套源码哈希。

实施中发现并修正：函数提取后遗漏的旧名称调用；新增测试中 Mac `/var` 与 `/private/var` 规范路径的期望值。没有降低原测试标准。

参数合并、MDP 派生和 GRO 写出三个提取算法的函数正文与改动前保持一致。新增只读脚本 `tests/audit_asset_dependencies.py` 检查七个实验，拆分前后及真实计算后记录一致：

- 19 个不同配置文档；
- 19 个不同源资产文件；
- 所使用冻结库的 27 个文件，包括完整力场树和构建辅助库；
- 每个实验的解析内容身份及已声明库哈希。

审计依据真实配置解析和内容哈希，不以文件名或“能打开”判断参数相同。`git diff --check` 通过；案例目录和原 examples 无 Git 内容差异。

## 真实计算结果

使用已有 Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4。平台为 macOS CPU，2 线程，未使用 PowerShell、GPU 或旧正式生产入口。

| 已有示例 | 实际组成 | 原子数 | 独立接触对照 |
|---|---|---:|---|
| `packed_zil_water` | ZIL 2、SOL 2941 | 8901 | 21 帧一致 |
| `packed_ions_water` | CAT 2、ANI 2、SOL 2941 | 8905 | 21 帧一致 |
| `packed_mixture_water` | ZIL 1、CAT 1、ANI 1、SOL 2939 | 8897 | 21 帧一致 |
| `packed_zil_dry` | ZIL 2，无水 | 78 | 11 帧一致 |

四例均完成构建、EM 和原有短动力学阶段；水体系共 8 ps MD，无水回归沿用既有短协议。独立最小镜像逐帧算法与核心分析一致，分析前后原 Run 文件身份不变。接触值一致仅验证算法和管线，不能据此声称平衡、结合自由能或材料性质成立。

首次四例脚本总耗时约 68.55 秒，输出约 76.46 MB；限定 30 分钟、1 GiB，不含后续独立补测的统计。预算检查发生在任务交接处，子命令仍使用现有有限超时及退出宽限，不宣称操作系统级硬截止。

### 检查点补测与保留的覆盖不足

首次四例验收中的 1 秒调用只触发了进入下一阶段前的预算检查，没有产生动力学中途检查点。原始记录如实保留 `actual_checkpoint_interruption=false`，不将其冒充真正恢复验收。

另建一个独立三组分 Run，以同一模型/协议完成 EM 后，用 2 秒预算进入 NVT：实际在第 640 步、1.28 ps 中断，目标为第 1000 步、2 ps。随后通过原检查点 `-cpi/-append` 完成 NVT 及后续全部阶段，最终独立分析 21 帧一致，原 Run 未被分析修改。

对中断 Run 的新隔离副本执行四种负例：源参数改动、检查点改动、轨迹改动、错误重启，全部明确拒绝；拒绝没有创建额外执行 attempt。原 Run 与原数据不参与篡改。

已将 `verify_architecture_a.py` 的预算改为 2 秒，并要求存在实际中断 seal，否则明确失败。该修正使用上述独立补测验证相同核心调用；没有再次整批重跑四个场景。不同硬件上若仍无法产生真实中断，应报告覆盖缺口，不能自动延长协议或改种子。

## 证据位置与复查

原始证据位于独立临时目录 `/private/tmp/materiasim-architecture-a.iBCyOd/`，未加入 Git；这是临时工程证据，不是长期科研数据备份。

- 四例清单、Run 引用与分析：`evidence/acceptance.json`。
- 运行前后依赖：`evidence/dependencies_before.json`、`evidence/dependencies_after.json`。
- 首次覆盖不足记录：`evidence/mixture_interruption.json`。
- 补测完成 Run：`checkpoint-runs/packed_mixture_water-6492c3936c804cc6a5a855b891922bd6/`。
- 中断时完整且未篡改的隔离副本：`checkpoint-guards/restart_refused/`，其 NVT seal 保留第 640 步的证据。
- 负例：`checkpoint-guards/guard_results.json`。
- 补测独立分析结果：`checkpoint-audit.json`。

当前实际入口，从 `materials_simulation/` 执行：

```sh
../zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -v

PYTHONPATH=. ../zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  tests/audit_asset_dependencies.py examples/packed_mixture_water.json
```

真实验收脚本是 `tests/verify_architecture_a.py --output <新的仓库外目录>`；它会启动限定短模拟，不是纯查询。审计脚本只输出 JSON，不创建 Run。

## 未完成项

A 批已完成本机工程验收。B—D 的包安装与资产迁移、统一研究包、批次登记和比较尚未实施；E—F 的 GPU/长任务及材料扩展也未实施。现有分析环境缺少 wheel，隔离构建工具安装尚待用户确认，未因此修改当前环境。

Linux、真实 GPU、跨平台检查点迁移、科学平衡与物性均未验收。重构改变源码身份；既有 Run 可以只读检查，不允许用新版强行恢复旧源码创建的 Run。

迁移说明（2026-09-15）：本记录从 `materials_simulation/docs/2026-09-15__architecture-a-acceptance.md` 移至 `docs/validation/`。正文的运行命令、包名、阶段完成范围与绝对证据路径是当时的历史事实；当前入口以根 README 为准。只修正相对文档链接，不改写 Run。
