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

生成 Run、轨迹、检查点和分析必须使用明确的仓库外目录。旧 Run 可以只读检查；源码改变后不允许绕过身份校验续跑。当前仅支持 `engineering_smoke`，不因可安装就宣布科学验证、GPU 或新材料支持完成。

从仓库根运行测试（使用已有分析依赖的解释器）：

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -v
```

单实验入口见[模拟指南](docs/guides/simulation.md)，多个条件与重复见[研究包指南](docs/guides/research.md)。首个可运行研究包是 [ZIL 数量工程验收](studies/zil_count_smoke/README.md)：

```sh
materiasim research validate studies/zil_count_smoke/research.json
materiasim research plan studies/zil_count_smoke/research.json
```

上述命令只预检和预览，不启动模拟；保存与执行必须指定新的仓库外输出位置。A—D 当前受限子集已完成，98 项测试及四任务／四场景、实际批次检查点恢复通过，见[B—D 验收](docs/validation/2026-09-15__architecture-bcd-acceptance.md)。完整进度见[架构方案](docs/plans/2026-09-15__architecture__simulation-package-and-research-bundles__implementation-plan.md)。当前研究比较仅支持同协议的组分接触工程汇总，不支持任意字段扫描或科学置信区间。
