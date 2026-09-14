---
type: implementation-plan
status: draft
plan_kind: implementation-plan
created: 2026-09-14
last_updated: 2026-09-14
owner: materials_simulation
scope: 无 GPU 环境下实现 CPU/GPU 共用执行层、受控长任务与服务器验收准备
implementation_status: 仅方案；未实施；本机无可供本任务验收的 GPU，Linux/GPU 待服务器实测
parent_plan: 2026-09-14__multicomponent-multiscenario__implementation-plan.md
supersedes: []
---

# CPU 测试与小任务、GPU 主力计算：执行层实施方案

## 1. 目标与决策

在当前 Mac 上完成项目开发、CPU 回归和 GPU 调用逻辑测试，以后将同一份代码部署到 Linux GPU 服务器，再完成真实 GPU 验收。现在没有 GPU 不阻止开发，但不能因此宣称 GPU 已可用或已经通过验收。

保留 `materials_simulation/` 这一套模拟核心。GROMACS 负责数值计算和 GPU 加速；MateriaSim 负责配置校验、资源选择、启动停止、证据记录和结果检查。不编写 CUDA，不复制 CPU/GPU 两套 runner。

本方案是[多组分＋多场景实施方案](2026-09-14__multicomponent-multiscenario__implementation-plan.md)的执行层补充，不替代其材料扩展主线，也不把 M3—M6 未完成能力标记为完成。当前仅授权编写文档；后续实施、安装和实际计算分别按授权执行。

### 1.1 首版边界

- 运行方式：原生 macOS/Linux、单机 GROMACS；CPU 或单 GPU 配合 CPU。
- Mac：开发、输入检查、CPU 短测及已有支持范围内的小任务。
- Linux 服务器：同一核心独立构建新 Run、GPU 短测、验收后的长任务。
- 首个 GPU 后端在服务器硬件确定后锁定；若为 NVIDIA，优先验收 CUDA 构建，不提前宣称 AMD/Intel/Apple GPU 已支持。
- GPU 主要承担适合卸载的动力学计算；构建、预处理、最小化和分析不要求全部上 GPU。
- 无服务器时完成“本地实现与 CPU 验收”，不是“GPU 生产就绪”。

### 1.2 不属于本轮

不新增 LAMMPS/OpenMM，不写远程 SSH 控制器，不接 Slurm，不做多 GPU、多节点 MPI、自动资源寻优或多任务调度；不安装 CUDA、驱动或服务器软件；不迁移 Mac 检查点到 Linux；不重参数化或新增材料模型；不清理旧目录、历史 Run 或 ML 环境。

## 2. 当前代码基线与缺口

下列是 2026-09-14 的源码事实，不是实现后的能力描述。当前实际入口见[模块 README](../../materials_simulation/README.md)。

| 现状 | 证据 | 必要变化 |
|---|---|---|
| `mdrun` 固定 `-nb cpu -pme cpu`、一个 thread-MPI rank | [gromacs_stage.py](../../materials_simulation/materials_sim/gromacs_stage.py) | 按执行配置生成 CPU/GPU 参数 |
| 只有线程与墙钟 CLI 参数，没有资源配置文件 | [cli.py](../../materials_simulation/materials_sim/cli.py) | 加入独立资源入口，冻结解析结果 |
| 只接受 `engineering_smoke` | [config_v2.py](../../materials_simulation/materials_sim/config_v2.py) | 区分用途、科学批准与资源预算 |
| MD 每段最多 2,000 步，并强制每 100 步输出 | [protocol.py](../../materials_simulation/materials_sim/protocol.py) | 短测约束与非短测协议分开 |
| 最多 8 线程、墙钟参数 600 秒 | [execute.py](../../materials_simulation/materials_sim/execute.py) | 变为明确的执行预算，不取消有限预算原则 |
| 只解析引擎版本、路径、平台与二进制哈希 | [gromacs.py](../../materials_simulation/materials_sim/gromacs.py) | 增加构建能力、请求设备和实际卸载证据 |
| 执行要求引擎身份与构建时一致 | [execute.py](../../materials_simulation/materials_sim/execute.py) | 保留保护；首版在目标服务器新建 Run |
| 检查点间隔为 0.01 分钟；阶段输出保留完整副本 | [gromacs_stage.py](../../materials_simulation/materials_sim/gromacs_stage.py) | 按任务设置间隔与存储预算 |
| 每个分析任务复制输入轨迹并核查哈希 | [analysis.py](../../materials_simulation/materials_sim/analysis.py) | 保留原 Run 保护，明确复制成本与容量上限 |

目前的原子数、组分数、盒形、势函数和积分器限制还包含构建器与模型能力边界，不能全部当成 CPU 限制删除。例如装填几何检查包含两两距离计算；提高规模上限前须评估复杂度。本轮先保持已验收体系规模，优先支持更长时间的运行。

## 3. 统一的配置责任

### 3.1 三类信息分别管理

| 类别 | 内容 | 禁止混入 |
|---|---|---|
| 模拟定义与协议 | 组分、力场、场景、阶段、步长、总步数、速度交接、轨迹/能量输出频率 | 本机 GPU 编号、工具绝对路径 |
| 任务用途与审查 | 跑通测试、模型验证、正式采样；目标与批准的范围 | “有 GPU 就已经科学可靠” |
| 执行配置 | 引擎位置、CPU 线程、GPU 选择、分阶段卸载策略、墙钟/检查点/存储预算 | 自动改变温压、力场或步长 |

输出频率影响后续科学分析，是协议的一部分；检查点保存间隔属于执行恢复策略。物理时间与墙钟时间分别记录，不用运行几分钟推断模拟了多少 ps。

CPU 可跑正式小任务，GPU 也需要短测。两者共用模型、构建、协议、状态机与分析。

### 3.2 执行配置的首版字段（拟议接口，当前不能执行）

- `schema_version`：配置版本。
- `device`：仅 `cpu` 或 `gpu`，不提供整项静默自动回退。
- `threads`：正整数，检查目标机器实际可用资源。
- `gpu_id`：单个可见设备选择；只有 GPU 模式允许，解释为该进程可见编号而非集群全局编号。
- `gromacs_executable`：本地程序定位，内容身份单独记录。
- `dynamics_offload`：非键、PME、键合、更新的执行策略；仅接收已实现白名单，不开放任意 shell 参数。
- `attempt_wall_seconds`、`termination_grace_seconds`、`checkpoint_interval_minutes`：一次执行预算及恢复策略。
- `max_attempts`、`total_wall_budget_seconds`：防止 agent 通过反复 resume 绕过总任务预算；不自动循环重试。
- `max_output_bytes`、`min_free_bytes`：输出和磁盘安全余量。
- `build_wall_seconds`、`analysis_wall_seconds`：独立阶段预算，不把所有命令都套用短测固定超时。

具体数值由本机短测配置或目标服务器任务预算给出，不把某型号 GPU、显存容量、长任务时间写进框架默认值。CPU 短测可以保留现有安全默认；非短测必须显式给出预算。

配置解析是普通 Python 数据结构与纯函数，不引入插件工厂、任务数据库或通用调度框架。

### 3.3 用途与模型适用性不能混淆

拟支持 `engineering_smoke`、`model_validation`、`production` 三种用途，并分别实现完整校验，不只增加枚举。

- `engineering_smoke` 保留现有小规模与短步数限制，不产生科学通过结论。
- `model_validation` 可在人工批准的验证目标、协议与预算内运行候选模型；完整性、参数兼容与数值安全检查仍不可跳过。
- `production` 必须引用可追溯的模型适用范围、协议审查和目标环境工程验收记录；批准只针对具体组合和目的，不承诺结果正确或已收敛。
- 已有 `engineering_only` bundle 不改成“已验证”，也不能仅换 purpose 就自动获准正式采样。其扩展使用由独立、带内容哈希的审查记录明确允许的用途与范围；旧文件保持不变。
- 无 GPU 时可以实现上述校验，并用明确标识的测试夹具验证拒绝路径；不得给现有模型伪造批准记录。
- 执行完成、实际 GPU 使用、数值检查、平衡/采样和模型适用性分别记录。现阶段自动判断不了的科学项目仍为 `not_assessed`。

## 4. GROMACS 适配器的必要改动

### 4.1 参数生成与阶段策略

将参数生成提取成可独立测试的纯函数，输入为解析后的执行配置与阶段类型；不启动 GROMACS 就能检查最终参数列表。

- CPU 配置：明确选择 CPU 计算路径，避免机器有 GPU 就改变回归行为。
- GPU 配置：动力学非键计算明确要求 GPU；PME、键合和更新可按已支持策略选择 CPU/GPU/auto。局部 auto 的实际结果必须记录。
- 首版最小化明确走 CPU；这是预先声明的阶段策略，不是 GPU 失败后的回退。
- 首版一个 thread-MPI rank 配合单 GPU；外部 MPI 二进制先明确拒绝，不误用 `-ntmpi` 或擅自添加 `mpirun`。
- 不假定所有协议都支持 GPU update 或 PME；不因不支持就更改约束、积分器、温压耦合或相互作用模型。
- 不为满足 GPU 开关修改用户环境变量；继承的设备可见性与相关 GROMACS 变量需核对并记录白名单值。不得将整个环境写入清单，以免保存凭据。

参数职责依据 [GROMACS 性能与 GPU 分工说明](https://manual.gromacs.org/documentation/current/user-guide/mdrun-performance.html)。具体支持以目标版本、编译选项和实际协议为准，不能只看版本号。

### 4.2 环境检查分三级

1. **静态有效**：CPU 上可解析 GPU 配置、检查组合并生成参数；不要求当前存在 GPU。
2. **目标环境可尝试执行**：查询引擎构建能力、设备可见性和资源；无法识别时返回未知或阻止执行，不能伪报可用。
3. **实际使用已验证**：从真实 `mdrun` 日志核查请求与实际卸载分配，结合退出、检查点和数值证据判断。

扩展现有 doctor/capabilities/validate，不新增伪装成只读查询的 GPU 试跑。日志解析不支持或缺少实际分配证据时，GPU 要求不能记为通过。启动阶段尽早发现错误，运行后仍复核实际分配。

现在不安装 GPU 运行时；目标端 NVIDIA 查询工具缺失也不能简单等同于“没有 GPU”。查询工具仅作辅助，真实引擎运行是最终工程证据。

## 5. 长任务、恢复与存储

### 5.1 协议与预算

将现有短步数、时间/步数原点上限与固定输出频率整理为短测策略；非短测使用显式正整数目标与有限预算，保留数据类型、单位、状态交接和数值约束。时间/步数计算采用足够范围，不以删除所有校验实现长任务。

物理参数仍取自冻结协议；输出频率变化须记录并检查是否足以支撑请求的分析。非短测不再被强制写成每 100 步输出。禁止为了 CPU 测试而暗改正式协议；短测派生配置与正式配置各自保存并建立来源关系。

正常时间预算到达时，先要求引擎在安全边界写检查点，再给有界退出宽限；强制杀死、缺少检查点、磁盘写入失败不能标记为普通可恢复中断。GROMACS 的最大运行时间并非整个工作流的精确硬截止，编译、封存和分析预算另计。

### 5.2 最小可行存储路线

首版保留已验证的 `-cpi/-append`、每次 attempt 证据和独立分析输入保护，不在同一轮同时重写成分段轨迹存储系统。

必要补充：

- 检查点间隔由配置明确给出，不把测试的 0.01 分钟带入所有任务。
- 构建前估计帧数、产物规模和副本成本；估计值标注不确定性，不能替代实际空间检查。
- 执行、封存、续跑与分析复制前检查剩余空间及配置预算；把完整历史副本的累计开销计入。
- 输出大小和累计 attempt 数有上限，运行中周期检查；接近预算时请求安全停止并留出检查点空间。
- 分析配置预检输入容量；超过已支持的安全容量时在复制前拒绝，不能无限复制或自动删除历史输出。
- 不用可被原地 append 修改的硬链接伪装历史快照。

这个选择优先保证可恢复性，但**首版不是无限规模、大轨迹高效分析平台**。它只对明确存储预算内的长任务开放。若服务器目标轨迹超出该路线的可接受开销，再单独实施不可变分段产物、分段校验与只读分析缓存，不能靠关闭证据保护解决。

检查点、append 与输出一致性依据 [GROMACS 长模拟管理](https://manual.gromacs.org/documentation/current/user-guide/managing-simulations.html)和 [mdrun 参数说明](https://manual.gromacs.org/documentation/current/onlinehelp/gmx-mdrun.html)。

## 6. Run 身份与历史兼容

新增可执行 Run 采用明确的新格式版本（拟 v3），分别保存模拟定义哈希、执行配置哈希、实际环境记录和用途审查引用；不能把新字段补写进历史 manifest。

- v1/v2 历史读取、报告与外部重分析保留；用对应原始实现执行旧 Run，不建立第二套旧 runner。
- 现有 v2 示例仍允许校验；实现显式转换到新配置并写新文件，来源哈希可追溯。转换不启动计算，不覆盖原配置。
- 新建 Run 使用新格式；若新 CLI 暂不执行旧格式，错误必须说明转换入口与历史读取仍可用，不能突然吞错或自动迁移。
- 同一 Run 的普通 resume 保留协议、输入、引擎和实现身份检查，并验证冻结的资源策略；每次实际环境另记。
- 不把执行路径混入材料内容身份。GPU 型号/可见编号/实际分配属于执行证据，不是化学身份。
- 换服务器、换构建或改协议先建立新 Run；不提供跳过身份保护的 force 参数。
- Mac 短测和 Linux 正式计算可关联同一个实验来源，但各自有独立 Run 身份，不能伪称二者是一条连续轨迹。

详细兼容约束遵循[项目兼容性规则](../ai/COMPATIBILITY_POLICY.md)。

## 7. 文件改动地图

以下既有文件为真实路径；“拟新增”仅是后续实施建议，不表示当前已有这些模块或 API。

| 文件/位置 | 修改职责 |
|---|---|
| `materials_simulation/materials_sim/cli.py` | 新增执行配置入口、静态与运行环境状态区分；参数冲突明确拒绝 |
| `materials_simulation/materials_sim/schema.py`、`config_v2.py` | 版本路由、旧配置校验与显式迁移边界；新语义不塞回历史读取器 |
| 拟新增 `execution_profile.py`、`config_v3.py`，位于同一包内 | 严格解析资源与新实验约定；不引入通用插件体系 |
| `materials_simulation/materials_sim/protocol.py` | 用途专属预算与输出策略，保留有效物理参数及来源 |
| `materials_simulation/materials_sim/gromacs.py` | 构建能力、允许的环境证据、受控停止与预算监测 |
| `materials_simulation/materials_sim/gromacs_stage.py` | 参数生成、CPU/GPU 阶段策略、实际卸载核查、检查点设置 |
| `materials_simulation/materials_sim/execute.py` | 消费统一资源配置；累计预算、运行状态与恢复，仍不解释引擎细节 |
| `materials_simulation/materials_sim/build.py`、`state.py`、`records.py` | 新 Run 格式、三类身份和历史只读兼容 |
| `materials_simulation/materials_sim/analysis.py` | 复制前预算检查，不修改原轨迹或假造新观察量 |
| `materials_simulation/tests/` | 参数、预算、恢复、兼容及环境负例；新增测试按职责拆分 |
| `materials_simulation/examples/` | 新 CPU 短测与 GPU 候选资源配置；旧案例保留，服务器路径不写入通用示例 |
| `materials_simulation/README.md`、相关 `AGENTS.md` 与本方案 | 同步真实命令、能力状态、限制与后续验收记录 |

若文件增大，应按已出现的参数生成、预算或版本读取职责拆分，避免将所有逻辑堆入 CLI 或执行器。源码新增函数和实质修改函数补足 docstring。

## 8. 实施批次与退出条件

| 批次 | 无 GPU 现在能做的工作 | 退出条件 |
|---|---|---|
| E1 配置与身份 | 新格式、资源配置、用途检查、迁移与历史读取 | CPU/GPU 配置可静态检查；非法组合拒绝；历史不改写 |
| E2 执行适配 | 参数生成、设备证据、阶段策略、CPU 核心回归 | CPU 真跑通过；无 GPU 时请求 GPU 明确拒绝；模拟日志测试不标为硬件验收 |
| E3 长任务基础 | 非短测协议、时间/存储/attempt 预算、停止与续跑 | 在小体系有限预算内验证非短测代码路径及真实中断恢复；未做长时负载测试须明示 |
| E4 本地交付 | 示例、操作说明、服务器检查与验收流程 | 标记“本地已实现/CPU 已验收；Linux/GPU 未验收” |
| E5 服务器验收（以后） | 目标环境安装另行授权，真实 GPU、恢复和 CPU/GPU 对照 | 只对实测的硬件、引擎构建、协议和体系发布支持结论 |

E1—E4 可以在现在的环境完成，不依赖选择新材料；仍只使用现有真实模型做受限工程回归。E5 不是通过 mock 可以提前完成的任务。

## 9. 验证矩阵

### 9.1 本机无需 GPU 的测试

- 现有配置/模型/拓扑与科学参数保护回归；CPU 参数不意外启用 GPU。
- GPU 参数生成和阶段策略、错误设备编号、非法 CPU/GPU 字段组合。
- GPU 构建不可用、设备未知、日志未使用 GPU、日志格式不支持时的明确失败；使用测试夹具并标识来源。
- 配置校验不调用 mdrun、不安装软件、不创建 Run；请求 GPU 不回退 CPU。
- 墙钟和总预算、attempt 上限、检查点间隔、输出频率、存储不足和复制失败。
- v1/v2 历史读取、显式迁移、新格式篡改拒绝、恢复身份一致性。
- 多次恢复的步数/时间衔接、输入速度继承和原资产不变。
- `engineering_only` 不能通过修改 purpose 直接进入 production；未审查、范围不符、哈希过期均拒绝。

### 9.2 Mac CPU 真实小量验收

在未来获得实施与小量验收授权后，复用现有环境，不新装依赖。默认回归预算沿用已有短测量级；验证非短测路径时也使用小体系和有限的显式预算，不能运行完整生产协议。

已有测试命令（不是本次已执行记录）：

```sh
cd /Users/niezhidong/Desktop/MateriaSim/materials_simulation
../zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -v
```

真实检查至少包括构建、最小化、动力学、主动预算中断、原目标恢复、独立分析与只读历史访问。保存本次实际测试数和 Run 位置，不沿用旧“66 项通过”当成新版本测试结果。

### 9.3 未来 Linux GPU 验收

1. 确定 GPU 型号、驱动、GROMACS 精确版本和编译选项、可用 CPU/显存/磁盘，按授权建立独立环境。
2. 校验模型文件及间接力场库；若库哈希不同，先核对来源和内容，不能改哈希绕过检查。
3. 在服务器新建小量 CPU 与 GPU Run。CPU/GPU 数值对照使用相同冻结初态、有效协议和匹配计算设置，不能独立随机重建后直接比较。
4. 验证 GPU 实际参与、完整阶段、数值日志和输出；检查点恢复在同一目标环境真实测试。
5. 做固定构型的能量/力对照及适用的短程检查。误差标准在执行前按模型、精度和计算路径确定，不要求长轨迹逐帧或逐字节相同。
6. 追加一项受控较长运行，检查停止、I/O、容量及性能证据；不能用 Mac 小测试代表服务器长期稳定性。
7. 分开记录工程验收与平衡/物性验证。GPU 更快不证明采样充分或模型可靠。

## 10. 风险、回退与完成口径

- **无硬件误判**：本地完成后 GPU 状态保留未验收；运行环境检查不能只看模拟输出夹具。
- **范围膨胀**：单 GPU 优先；服务器调度、更多引擎和材料扩展另开明确任务。
- **放大旧短测假设**：不能只去掉步数上限；同时检查输出、检查点、累计预算和存储成本。
- **身份保护变弱**：新版本读写分离；不修改历史记录、不自动转换旧 Run、不关闭哈希检查。
- **科学用途被误升级**：资源配置不授予模型适用性；现有工程候选只在明确授权范围内使用。
- **生产轨迹超出存储路线**：明确拒绝超预算任务并报告限制；不删除历史副本或伪造只读快照。

回退保留旧源代码版本、配置和 Run；实现出错时停止创建新格式运行，用原版本读取/执行其支持的历史任务。不在本轮自动执行 Git 回退、删除输出或覆盖环境。

本地完成口径：E1—E4 实现与 CPU 实测通过，GPU 相关纯函数和失败路径有测试，服务器操作步骤齐备；明确 Linux/GPU 以及长期负载尚未验收。

最终执行层完成口径：E5 对指定服务器和既有模型子集通过，可按批准的协议与预算运行 CPU/GPU 任务。它仍不意味着混合溶剂、聚合物、固相、界面或模型科学验证自动完成。

## 11. 本次文档交付记录

2026-09-14：仅编写本方案并关联原实施方案；没有修改模拟源码、安装依赖、启动 MD 或执行 GPU 测试。本文的拟议字段、模块和新版本均不是当前已经可用的接口。
