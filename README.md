# MateriaSim

原生 macOS/Linux 路线的可追溯材料模拟工具。当前数值引擎是 GROMACS，已实现的模型范围是 ZIL/CAT/ANI 与 TIP3P 的受限工程短测；不是任意材料、力场或相态都可运行的平台。

## 开发安装

在独立 Python 3.9+ 环境中安装本项目。核心只用标准库；分析可选依赖沿用当前已验收版本，不自动安装 GROMACS 或 Packmol。

```sh
python -m pip install -e .
materiasim doctor --packmol packmol
materiasim validate examples/packed_mixture_water.json
```

需要分析时，在对应环境安装 `.[analysis]`；跨平台自行建立环境，不复制 Mac 二进制到 Linux。当前 Python/分析依赖组合的实测平台为 macOS，Linux 和 GPU 待验收。

## 目录职责

- `src/materiasim/`：唯一模拟核心与命令入口。
- `catalog/`：共享模型、相互作用包、协议与冻结输入；不包含安装态力场库。
- `examples/`：最小实验配置，引用共享资产。
- `studies/`：研究源码包，组织条件与重复，不复制引擎。
- `tests/`：单元与真实工具验收。
- `docs/plans/`：实施方案；目标能力与实际完成进度分开记录。
- 两个旧案例目录与 `materials_simulation/`：历史来源、原环境和验收资料，未经授权不清理。

生成 Run、轨迹、检查点和分析必须使用明确的仓库外目录。旧 Run 可以只读检查；执行依赖或原生引擎身份改变后不允许绕过校验续跑。现有模型示例仍是 `engineering_smoke`；model_validation/production 已有用途证据门禁，但不会自动批准现有模型，不因可安装就宣布科学验证、GPU 或新材料支持完成。

从仓库根运行测试（使用已有分析依赖的解释器）：

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -v
```

完整 MD 流程、GROMACS／开源工具／本项目的职责及不同材料场景的配置路线，见[MD 工作流程与工具边界指南](docs/guides/md-workflow-and-tool-boundaries.md)；其中候选接入项不代表已实现能力。

科学依据、算法定义、模型兼容、参数语义与验证方法见[科学知识库](docs/knowledge/README.md)；当前支持范围见[能力矩阵](docs/knowledge/platform/capabilities.md)，后续工作见[计划索引](docs/plans/INDEX.md)。知识参考已建立，不表示聚合物、纳米材料等功能已接入，也不构成生产用途批准。

单实验入口见[模拟指南](docs/guides/simulation.md)，多个条件与重复见[研究包指南](docs/guides/research.md)。首个可运行研究包是 [ZIL 数量工程验收](studies/zil_count_smoke/README.md)：

```sh
materiasim research validate studies/zil_count_smoke/research.json
materiasim research plan studies/zil_count_smoke/research.json
```

上述命令只预检和预览，不启动模拟；保存与执行必须指定新的仓库外输出位置。A—D 的 98 项测试与历史验收见[B—D 记录](docs/validation/2026-09-15__architecture-bcd-acceptance.md)，保留为当时事实。当前 Research v2 已能组织预建/装填场景、显式种子槽、无分析或已有接触分析，见[双场景双分析示例](studies/mixed_builders_smoke/README.md)；另已接入 [mass_density 整盒密度／体积](docs/knowledge/algorithms/bulk_density.md)，消费封存 EDR 而非猜测原子质量。不支持任意字段扫描或科学置信区间；新增分析不代表乙醇混合体系已验证。

当前[可扩展框架方案](docs/plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)已落地 Experiment/Run v3：组分/模型、带格式资产、边界/构建器、物理协议与 CPU 执行配置分开表达；现有引擎/构建/分析消费统一交接契约。v2 配置仍可新建任务，经确定性转换生成 v3 Run，保留原文与来源报告；旧 Run 不改写、不由新代码强行续跑。[原生 v3 示例](examples/v3/packed_zil_water.json)可直接校验与构建，`materiasim migrate examples/packed_zil_water.json` 只预览转换。

最新 **193 项测试、16 个 Mac CPU Run／58 个阶段**通过，见[本地框架交付验收](docs/validation/2026-09-15__framework-local-delivery-acceptance.md)。覆盖既有研究回归、真实中断恢复、无分析任务、用途软件夹具、归档搬迁/损坏拒绝，以及源码包→wheel→隔离安装→仓库外构建/运行。安装态分析另复用现有分析依赖验证，未新装第三方依赖。[账本](docs/validation/2026-09-15__control-journal-integrity-acceptance.md)、[研究与资源控制](docs/validation/2026-09-15__research-execution-acceptance.md)、[v3](docs/validation/2026-09-15__v3-contracts-acceptance.md)、[组件边界](docs/validation/2026-09-15__framework-component-boundaries-acceptance.md)和[编译交接](docs/validation/2026-09-15__prepared-stages-acceptance.md)保留为历史记录。

execution_profile v2 已统一控制构建/执行/分析的预算，账本独立位于 Run 旁 `.materiasim-operations/<RunID>/`，分析不改写 MD Run。单 CUDA GPU 的非键/可选 PME 卸载是已实现但未硬件验收的候选路径；Mac CPU 实测不能替代 Linux/GPU 验收。旧 CPU profile v1 的解释保持，新冻结计划版本为 3，研究定义与 Run 版本独立。

新控制账本使用独立 contract_version=2，验证请求/结果哈希、事件顺序、计费和输出清单；进程退出后仍检查预算。旧控制账本 v1 只读，不原地补证据或追加受监督操作。完整性哈希不等于签名、生产审批或硬配额。

本方案的 **P4/P5/P6 本地框架范围已收口**：profile v3 冻结工具定位、用途证据和显式采样；复制前容量核对、独立封存代次、分析隔离、受监督进程组回收及只读归档；agent JSON 封装和安装态交付。用法与具体边界见[模拟指南](docs/guides/simulation.md)。`materiasim tools` 只读列出命令，`--json-envelope` 启用版本化响应，`archive` 只向明确新目录复制完成态证据，`verify-archive` 核查搬迁后的副本。

“本地框架完成”不等于所有材料/环境已验收：Linux/GPU、长负载、混合溶剂、聚合物、固相与纳米材料仍待具体接入和验证。用途审核是本地可追溯声明，不是认证签名；容量检查不是硬配额，进程组回收不覆盖最外层监督器本身被 SIGKILL；只读归档不是活动任务或跨平台检查点迁移服务。当前 engineering_only 模型不会自动进入 production。
