# 非共价离子对水化计算

本项目比较一个非共价离子对与已完成共价 ZIL 的紧密结合水数。

- 阳离子：`CC[N+]1=CN(CCOCCOC)C=C1`，`CAT`，净电荷 `+1`；
- 阴离子：`CS(=O)([O-])=O`，`ANI`，净电荷 `-1`；
- 目标体系：`CAT 1` + `ANI 1` + 2957 个 AMBER TIP3P 水，4.5 nm立方盒，298 K、1 bar；
- 参数化：GAFF2 + AM1-BCC；生产引擎：GROMACS。

当前仅执行参数化、体系构建与短程 smoke 验收。正式生产必须等待单独的用户确认；本目录的任何smoke结果都不作为离子对水化数结论。

完整方案与风险控制见上级项目的 `zwitterion_hydration_md/ION_PAIR_HYDRATION_PLAN.md`。

## 跨平台正式入口

正式生产入口使用 Python 3.9+，可在 macOS 和 Linux 上运行。脚本默认从 `PATH`
查找 `gmx`，运行目录和已经验收的 `solvated.gro` 必须显式传入：

```bash
python3 formal/run_production.py --threads 8 start \
  --run-directory /data/ion_pair_hydration_runs/run_001 \
  --solvated-gro /data/frozen_inputs/ion_pair_solvated.gro
```

如果 GROMACS 不在 `PATH`，在子命令前额外传入
`--gmx /opt/gromacs/bin/gmx`。继续已有生产轨迹时：

```bash
python3 formal/run_production.py --threads 8 resume \
  --run-directory /data/ion_pair_hydration_runs/run_001
```

迁移机器时必须复制完整运行目录或冻结输入，并先核对 SHA-256；不得重新生成或改写
已验收的拓扑、MDP 和初始溶剂化坐标。
