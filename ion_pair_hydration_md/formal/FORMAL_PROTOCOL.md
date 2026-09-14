# 离子对正式生产冻结说明

**授权日期：** 2026-09-09  
**正式重复：** `run_001`，单条连续轨迹。

## 已冻结的体系

- 溶质：`CAT 1` + `ANI 1`；两个分子保持独立、无跨离子共价项；总电荷为 `0 e`。
- 参数：GAFF2 + AM1-BCC；AMBER TIP3P 水。
- 初始盒：`4.5 × 4.5 × 4.5 nm³`，`2957` 个水，`8912` 个原子。
- 温压条件：`298 K`，`1 bar`。
- 平衡：EM → 1 ns NVT（固定速度种子 `192837`）→ 5 ns NPT（C-rescale）。
- 生产：10 ns NPT，`2 fs` 时间步，Parrinello--Rahman 压强耦合，v-rescale 温控，PME 与 `1.2 nm` 实空间截断。
- 输出：压缩轨迹每 `2 ps`，能量/日志每 `10 ps`，检查点每 `10 min`。

正式运行目录由 `run_production.py start --run-directory` 显式指定，已验收的初始溶剂化坐标由 `--solvated-gro` 传入。启动脚本将复制已验收的拓扑与初始溶剂化坐标；冻结的 `system.top` 明确写入 `CAT 1`、`ANI 1`、`SOL 2957`，并在该目录产生 `FROZEN_INPUT_MANIFEST.txt`（SHA-256）。运行完成前不得修改运行目录中的输入文件。

本生产的预定义分析窗口为生产段 `5–10 ns`。紧密结合水的实际 RDF 截断将仅由该正式窗口确定；不沿用 smoke 轨迹或 ZIL 的数值截断。
