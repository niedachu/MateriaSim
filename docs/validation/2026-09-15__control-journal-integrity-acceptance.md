# 控制账本完整性：Mac CPU 工程验收

日期：2026-09-15。状态：本子批通过；P4/P5/P6 整体未完成，科学质量未评估。

对应[框架方案第 19 节](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)。本轮仅继续框架加固与小量验收，没有安装依赖、修改模型/MDP、提交或推送。

## 实际改动

- `runtime/journal.py` 分离控制证据校验：严格字段、类型、身份、实际事件目录、请求与结果、计费、状态及分析输出清单。
- 新控制账本 contract_version=2；请求包含序号和前次结算哈希，事件保存请求/结果哈希。manifest 绑定版本和控制 ID，工作进程接收前与操作结算后核查。
- 历史账本 v1 保持原字节、允许只读审计，不原地升级或追加受监督操作。它缺少的新字段不会回填；需要匹配的源码快照或新独立 Run 才能执行新的工作。
- 完整预扣保留到结算；未知交接拒绝。输出根/祖先符号链接拒绝；正常退出后仍检查墙钟、存储字节和磁盘余量。

控制账本版本不等于 execution_profile、研究定义或 Run 版本；这些科学/资源配置未修改。哈希用于检测损坏与不一致，不是签名或正式用途审批，也不能防有写权限者一致重写全部证据。日志全文不纳入这条哈希链。

## 测试与故障记录

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m unittest discover -s tests -q
```

改前 164 项通过；新增 `tests/unit/test_control_journal.py` 的 13 项后，共 **177 项通过**。覆盖有效新账本、旧记录只读、负数/布尔/非有限计费、请求/结果变化、错误预算/配置绑定、重复/错序/孤立事件、开放预扣、输出清单删除、manifest 绑定、符号链接和退出后的预算漏检。

首轮新测试有两个测试方法因辅助代码传入 inventory 不接受的 `.` 而失败（其中一个包含多个子例）；改用显式目录名后通过。没有改生产校验、删断言或跳过失败测试。元数据工作进程和驱动无关夹具均明确标为测试，不当作 MD 结果。

## 真实短程验收

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_research_v2 \
  --output /Users/niezhidong/Desktop/MateriaSim-runs/journal-integrity-20260915-01
```

沿用已有示例和已授权小量预算：14 任务，2 CPU 线程、串行、1800 秒、1 GiB；工程上限仍为 20,000 原子、EM 5,000 步、动力学每阶段 2,000 步。没有调用正式案例长协议。使用现有 Mac 原生环境，不安装或替换工具。

结果 **status=passed、pending=[]**。总计 **14 个 Run、54 个阶段；306.71 秒、292,005,073 字节（278.48 MiB）**。字节数是最终总报告写入前的目录采样，不是文件系统配额。运行前后源码身份一致。

- 8 个既有任务完成：6 个单实验，以及原研究格式的两个恢复任务；保留独立分析算法对照。
- 4 个双场景、双分析任务完成：新账本下的首个 NVT 在 240/1000 步、0.48 ps、8,912 原子时真实 SIGTERM 中断，原 Run 恢复到原目标；所有阶段各成功编译一次，没有替换 TPR。
- 2 个无分析任务完成：空观察量/汇总，没有创建分析目录。

本轮六个新全流程账本均为 contract v2，事件全部闭合：

| Run ID | 操作 | 计费秒数 |
|---|---|---:|
| research-33985ca5794d4ae4b6f01c37385cb783 | build/run/resume/analyze | 22.937 |
| research-82a47ec2dfcb4422b871ac0d5299c237 | build/run/analyze | 21.933 |
| research-ef0b595541a14ce89c70cc54fee8b833 | build/run/analyze | 22.766 |
| research-d8305c18402446d2822dff111170d5e6 | build/run/analyze | 21.931 |
| research-12080e5869fd44b696af4117ff092e3e | build/run | 23.056 |
| research-ded376f880284c97bda1dc5b0c71dc69 | build/run | 22.314 |

## 历史与科学输入保护

上一轮 `research-execution-20260915-01` 的 14 个 Run、6 份旧控制账本通过只读核查；全目录 2,686 个文件在检查前后字节相同，跨源码执行均按 Implementation changed 拒绝。未改旧 manifest、账本、结果或状态。

本轮六个既有单实验与上一轮比较，冻结 inputs、派生 MDP、protocol_overrides.json 逐字节一致。原 CAT/ANI 随机删水的历史限制未改变，不要求动态轨迹或重新加水初态逐位相同。没有调整力场、步长、温压、组分计数或科学分析定义。

## 证据与边界

明确证据根为 `/Users/niezhidong/Desktop/MateriaSim-runs/journal-integrity-20260915-01/`：

- acceptance.json：当前源码、资源、最终状态及新控制契约逐 Run 审计。
- existing/：8 个既有任务、177 项测试日志、编译/恢复和独立算法对照。
- mixed_recovery/：四任务批次、真实中断记录、恢复与双分析比较。
- no_analysis/：两任务无分析研究。
- 各 runs/.materiasim-operations/：绑定的请求、结果、结算和账本，不是可删缓存。

本轮按 [simulation-research 技能](../../skills/simulation-research/SKILL.md)使用有界短测、显式输出、保留全部任务和工程/科学边界。此记录不替代完整科研数据备份。

未验收：Linux/GPU、正式长负载、科学收敛、新材料。未完成：正式用途审批、非短测开放、精确复制前容量、封存副本保护、共享输出隔离、路径迁移、强杀进程树回收、安装态/发行包与 CLI/agent 全路径。当前成功不表示这些剩余事项已完成。
