# 双构建场景、双分析的工程研究示例

[automation.json](automation.json) 可交给[本地规则 Harness](../../docs/guides/harness.md)，经独立用户授权后运行；不因侧车存在就自动启动或扩大用途。

这是 Research v2 的可执行工程输入，不是新的材料科学研究结论。

- 预建 CAT×1/ANI×1 水盒与自动装填 CAT×2/ANI×2 水盒，每种两次显式重复。
- 沿用既有 CAT/ANI 模型、相互作用包和原短程协议；声明变化因素为场景及数量。
- 同时运行原水化接触算法与组分接触算法，分别比较水氧并集均值和唯一分子对均值，不混合单位。
- 预建路径只提供实际速度种子；装填路径另有 packing 种子。当前 `solvate -maxsol` 随机删水行为保持，不能把这些显式种子解释为对所有构建随机性的控制。
- 工程判据检查所有声明任务、阶段和分析完整。没有平衡剔除、自相关校正或科学置信区间；两次短重复不证明统计独立性。

已安装环境中只读预览：

```sh
materiasim research validate studies/mixed_builders_smoke/research.json
materiasim research plan studies/mixed_builders_smoke/research.json
```

保存和运行仍须显式指定新的仓库外位置，见[研究指南](../../docs/guides/research.md)。本例每任务使用 execution_profile v2：2 CPU 线程、单次执行 180 秒、执行累计 360 秒、最多 2 次执行、构建 600 秒、分析 120 秒、全流程 1200 秒、25 秒退出宽限、512 MiB 输出阈值、64 MiB 磁盘余量。批次另限制 4 任务、串行、1800 秒与 1 GiB；两层预算是包含关系，不相加计费。

各 Run 旁 `.materiasim-operations/<RunID>/` 保存全流程预算和控制证据，分析不会改写 MD Run。归档或搬移时须连同控制目录及独立分析结果保留；不能删账本后继续执行。

这些配置源于 `examples/cat_ani_smoke.json`、`examples/packed_ions_water.json`。不修改 catalog 资产或 MDP。Linux/GPU 与科学质量需要独立验收。
