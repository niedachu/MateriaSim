# MateriaSim

**面向多组分、多场景材料研究的可追溯分子模拟框架。**

MateriaSim 将材料模型、体系构建、模拟协议、研究任务和执行管理分开组织，让不同研究复用同一套计算与证据管理流程。GROMACS 负责底层分子动力学，MateriaSim 负责输入校验、任务编排、受控运行和结果追溯。

项目采用原生 macOS/Linux 路线，不绑定特定大模型或 agent 宿主。当前计算后端为 GROMACS；多材料扩展围绕共享组件和研究包推进，具体支持范围见下文。

## 核心能力

- **组合式实验定义**：独立描述组分与数量、材料模型、相互作用参数、场景与边界、模拟协议、分析任务和执行资源。
- **可复用研究包**：用统一结构组织研究问题、对照条件、显式种子和重复任务；单实验与批次研究共用计算核心。
- **可追溯执行**：冻结实际输入、参数资产、工具与源码身份，保存阶段产物、操作回执和预算账本；续跑前核对已有证据。
- **独立分析与归档**：分析结果不覆盖原 MD Run；支持完成态单 Run 的证据导出与完整性核验。
- **受控自动化**：Campaign 管理后台监督、预算、暂停、撤销和故障对账；本地 agent 接口提供受限摘要、逐操作许可、超时与人工接管。
- **科学知识与实施治理**：知识库记录模型兼容、算法假设、参数语义与验证方法；计划和验收记录分别管理目标与实际证据。

## 架构

```text
共享组件 catalog/ + 实验配置 examples/
                  │
       研究包 studies/：条件、种子、重复
                  │
       Campaign：授权、监督、决策与审计
                  │
       共用工作流：校验 → 构建 → 运行 → 分析
                  │
       GROMACS / Packmol / 分析器
                  │
       Run + AnalysisRun + 账本与证据
```

单实验和研究包也可以直接调用共用工作流，不要求启用 Campaign 或 agent。能力由现有引擎、构建器、场景和分析注册表组合；当前采用静态内置组件，不加载任意第三方插件代码。

| 目录 | 职责 |
|---|---|
| [`src/materiasim/`](src/materiasim/) | 配置契约、组件实现、工作流、研究编排、Harness 与 CLI |
| [`catalog/`](catalog/) | 共享模型、相互作用包、协议和输入资产 |
| [`examples/`](examples/) | 可校验的单实验配置 |
| [`studies/`](studies/) | 研究定义、条件配置与自动化侧车 |
| [`docs/knowledge/`](docs/knowledge/README.md) | 科学与平台知识库 |
| [`docs/guides/`](docs/guides/) | 使用指南与工具边界 |
| [`docs/plans/`](docs/plans/INDEX.md) | 实施方案与进度 |
| [`tests/`](tests/) / [`docs/validation/`](docs/validation/) | 自动化测试、真实工具验收与证据记录 |

历史案例目录保留来源资产和已有环境，不是另一套公共核心。新的 Run、轨迹、检查点与分析输出使用明确的仓库外目录；Git 管理源码与研究定义，不替代科研数据备份。

## 快速开始

### 环境与安装

使用独立 Python 3.9+ 环境，从仓库根安装：

```sh
python -m pip install -e .
```

核心 Python 包无第三方运行依赖。需要基于 MDAnalysis 的分析时，安装可选分析依赖：

```sh
python -m pip install -e '.[analysis]'
```

GROMACS 与 Packmol 是独立的原生工具，不会由上述命令自动安装。自动装填需要 Packmol；具体工具版本、平台环境与配置要求见[模拟指南](docs/guides/simulation.md)。macOS 与 Linux 分别建立环境，不跨平台复制虚拟环境或二进制。

### 检查环境与输入

```sh
materiasim doctor --packmol packmol
materiasim capabilities
materiasim validate examples/v3/packed_zil_water.json
materiasim research validate studies/zil_count_smoke/research.json
materiasim research plan studies/zil_count_smoke/research.json
```

以上命令只查询、校验或预览，不启动模拟。配置校验通过不等于模型已经科学验证。

### 选择执行方式

| 工作方式 | 入口与说明 |
|---|---|
| 单实验 | `build → run / resume → analyze → report`；见[模拟指南](docs/guides/simulation.md) |
| 条件与重复研究 | `research plan → run → status / compare`；见[研究包指南](docs/guides/research.md) |
| 固定任务后台自动化 | `campaign create → start → status / evidence`；见[Harness 指南](docs/guides/harness.md) |
| agent 受控推进 | 显式策略＋`agent-read / submit-decision`；见[本地 agent 接口](docs/guides/harness-agent.md) |

执行前明确新的仓库外输出位置、资源预算与用途。Campaign 还需要独立用户授权；agent 决策不能修改力场、扩充预算或绕过人工控制。接口不要求使用某个模型供应商，实际宿主接入和权限隔离需单独配置与验收。

研究包可参考 [ZIL 数量与重复](studies/zil_count_smoke/README.md)及 [CAT/ANI 双构建场景](studies/mixed_builders_smoke/README.md)。这些配置用于验证工程链路，不直接作为正式材料结论。

## 当前支持范围

| 领域 | 当前能力与边界 |
|---|---|
| 材料与构建 | 已接入 ZIL/CAT/ANI 模型、TIP3P 水体系、预建结构及按整数数量自动装填；支持已有模型的无水周期盒短测 |
| 协议与分析 | 最小化、线性动力学阶段、检查点恢复；水化接触、组分接触、整盒密度／体积分析 |
| 研究与自动化 | 显式条件和种子、串行批次、受限比较；本地规则与结构化 agent 决策接口已实现，Campaign 当前限 CPU 工程任务 |
| 计算环境 | macOS CPU 已实测；Linux 待验收。核心单 CUDA GPU 卸载为候选路径，尚未硬件验收 |
| 后续材料扩展 | 混合溶剂与通用盐配方、聚合物／大分子、纳米材料、固相／界面仍需模型、构建与场景接入 |

工程执行完成、采样充分、模型适用和科学验证是不同结论。现有示例主要为 `engineering_smoke`；正式用途的证据门禁已经实现，但不会自动把现有 `engineering_only` 模型批准为生产模型。

本地授权与哈希用于可追溯控制，不是身份认证或操作系统沙箱。真实 agent／宿主隔离、服务器长负载、部署级重启恢复，以及整个 Campaign 的便携导出仍有待补齐。详细状态以[能力矩阵](docs/knowledge/platform/capabilities.md)与[实施计划](docs/plans/INDEX.md)为准。

## 验证与开发

从仓库根、使用具备分析依赖的环境运行回归测试：

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -v
```

[本地 agent 协议验收](docs/validation/2026-09-18__harness-local-agent-acceptance.md)记录了 285 项测试、脚本 provider 驱动的 5 个真实 CPU Run 和隔离安装检查；[进程与存储专项](docs/validation/2026-09-17__harness-crash-storage-acceptance.md)记录监督器丢失、进程组丢失和隔离卷满盘测试。记录各自对应其源码与环境，不代表真实模型、Linux/GPU 或材料科学验证已通过。

开发与 agent 协作遵循 [AGENTS.md](AGENTS.md)：复用共用核心、保留原始科学输入、为行为变化增加测试，并同步能力边界。新增材料需要对应模型与参数证据，不能只增加一个配置名称就宣称支持。

## 文档导航

- [MD 工作流程与工具边界](docs/guides/md-workflow-and-tool-boundaries.md)：哪些由 GROMACS 提供，哪些由平台组织。
- [科学知识库](docs/knowledge/README.md)：理论、算法、模型、场景与验证方法。
- [配置与组件归属](docs/knowledge/platform/configuration_components.md)：材料资产、研究配置、知识和执行证据如何关联。
- [计划索引](docs/plans/INDEX.md)：后续开发与验收任务。
