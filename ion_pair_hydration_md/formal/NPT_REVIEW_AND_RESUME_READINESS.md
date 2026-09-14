# 正式 NPT 复核与生产续跑准备

**复核日期：** 2026-09-13  
**结论：** NPT 通过；生产 checkpoint 有效；可从现有生产段 `0.2576 ns` 无损追加至总 `10 ns`。

## NPT 复核

NPT 已完成 `5.000 ns`，完整轨迹为 `2501` 帧（0--5000 ps、每 2 ps），日志确认正常结束。对后 `4 ns`（1000--5000 ps）的能量统计为：

| 量 | 平均值 | 误差估计 | RMSD |
|---|---:|---:|---:|
| 温度 | 298.035 K | 0.038 K | 3.133 K |
| 压力 | 4.062 bar | 2.8 bar | 225.768 bar |
| 密度 | 987.526 kg m⁻³ | 0.2 kg m⁻³ | 5.002 kg m⁻³ |

小型 NPT 水盒的瞬时压力波动很大；温度和密度稳定，压力平均值在其统计不确定度内与 1 bar 相容。EM、NVT、NPT 和已开始的生产日志中未发现真实 LINCS 警告、NaN 或 GROMACS 致命错误。

## 已有生产段与 checkpoint

- 生产轨迹目前有 129 帧，从 0 到 256 ps，每 2 ps 输出。
- `prod.cpt` 可由 GROMACS 正常读取：8912 原子、步数 128800、时间 257.600 ps。
- 生产轨迹的最后写出帧为 256 ps，正好早于 checkpoint；`-append` 续跑将从 checkpoint 状态继续并保留既有文件，不会重建体系或重复写入已存帧。

## 续跑方式

正式输入、TPR 和 MDP 保持不变。只运行：

```powershell
gmx mdrun -deffnm prod -cpi prod.cpt -append -nt 8 -pin auto -cpt 10
```

其效果是从 0.2576 ns 接续到已冻结的总 10 ns，而不是重新开始生产。可执行脚本为 `formal/resume_production.ps1`；脚本尚未运行。
