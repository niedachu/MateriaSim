# 两性离子单分子水化模拟

本项目计算纯水（298 K、1 bar）中单个
`3-(1-(2-(2-methoxyethoxy)ethyl)-1H-imidazol-3-ium-3-yl)propane-1-sulfonate`
的第一水化层占有数。

- SMILES：`O=S(CCC[N+]1=CN(CCOCCOC)C=C1)([O-])=O`
- 力场：GAFF2 + AM1-BCC（AmberTools 24.8）
- 水模型：AMBER TIP3P
- 当前正式生产：1 个中间构象、总计10 ns；冻结的物理输入可在后续增加独立重复或延长同一连续轨迹。
- 正式入口：`scripts/run_production.py`（Python 3.9+，支持 macOS 和 Linux）

## 科学定义

每一帧分别按照磺酸根、醚氧和咪唑鎓区域自己的 RDF 第一极小值选择水氧，
再按水残基编号取并集。最终结果是该去重水分子数的时间平均、分布和统计不确定度，
不是固定化学计量整数，也不是 DSC、TGA 或 NMR 的实验结合水数。

正式截断距离必须由生产轨迹的位点 RDF 确定。内部短轨迹只用于验证程序，不能用于报告水化数。

## 最终运行入口

交付只保留一个正式生产入口：

```bash
python3 scripts/run_production.py --run-root /data/zwitterion_hydration_runs
```

该入口按配置建立正式水盒并执行 EM、1 ns NVT、5 ns NPT 和总计10 ns生产模拟。
它没有 `dry-run`、`smoke` 或 `production` 模式开关。启动前会强制检查正式拓扑、三个代表构象、
MDP、GROMACS 路径和验收标记；检查失败即终止。

内部环境检查、单元测试、短程贯通测试和 CPU/GPU 基准由项目实施阶段完成，不作为最终用户运行模式。

## 正式输入

以下文件未通过审核前，不允许启动正式入口：

```text
topology/zil.itp
topology/zil_extended.gro
topology/zil_intermediate.gro
topology/zil_folded.gro
topology/system.top
results/acceptance/ACCEPTED.json
```

禁止用 `system.top.template` 或任何占位电荷、原子类型和键合参数代替正式拓扑。

> 当前参数化状态：GAFF2 + AM1-BCC 已完成参数验收并冻结到 `topology/`；正式输入的
> SHA-256、4.5 nm/2957 水盒和单重复协议记录在 `results/acceptance/ACCEPTED.json`。
> 正式入口仅在该记录与现场文件哈希一致时运行。

内部 smoke 使用 1 个 ZIL 和 2957 个 TIP3P 水。采用短轨迹 RDF 的临时截断距离时，
后 100 ps 的去重水化数约为 16.6；该数字只用于检查分析链路，不是正式科学结果。

## 分析

- `gmx rdf`：位点 RDF 与累计配位数；
- `gmx hbond`：溶质—水氢键；
- `gmx select -os/-oi`：逐帧水氧数量和编号；
- `analysis/hydration_count.py`：MDAnalysis 独立去重计算；
- `analysis/hydration_core.py`：不依赖轨迹库的集合、统计和参考距离算法；
- `tests/`：已知答案人工体系与配置测试。

GROMACS 与 MDAnalysis 的逐帧去重水化数必须一致，才能接受正式分析结果。
当前 MDAnalysis 2.9.0 不能读取 GROMACS 2026.3 的 TPX 138 TPR；分析时使用原子顺序一致的
GRO 与 XTC，或升级并验证支持该 TPR 版本的 MDAnalysis。

## 数据位置

源代码、配置和最终汇总位于本项目目录。大型运行文件必须通过 `--run-root`
显式指定，避免把机器相关路径写进科学配置。脚本默认从 `PATH` 查找 `gmx`；
如果命令名或位置不同，传入 `--gmx`：

```bash
python3 scripts/run_production.py \
  --gmx /opt/gromacs/bin/gmx \
  --run-root /data/zwitterion_hydration_runs \
  --threads 8
```

每个重复使用独立目录，正式轨迹不会覆盖内部测试轨迹。
