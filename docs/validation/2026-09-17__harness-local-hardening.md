# Harness 本地规则加固验收

日期：2026-09-17。承接[首版验收](2026-09-17__harness-local-first-increment.md)，不覆盖其历史数字。基线仍为 `bee0d787c558f52a840f3c037812d1f2dc523d2e`，当前未提交／推送。本记录对应[方案](../plans/2026-09-17__harness__plugin-research-automation__architecture-plan.md) H0/H1 当前本地范围完成、H2 主要闭环加固；**不是整个方案完成**。

## 实现范围

- 真实内置注册表依赖排序、缺失／禁用／循环／单任务冲突校验，冻结所需分析依赖版本；不加载任意动态代码。
- 新 Campaign contract v2；子操作 build/run/resume/analyze 准入前检查权限和暂停。已准入的操作允许安全收尾，不承诺立刻暂停 GROMACS 阶段。
- 已核验中断走显式恢复，保存原 Run／检查点；恢复前核查上次进度和工作文件哈希，删除旧进度不能变成新建任务。
- 明确错误类别；未知错误不猜原因、不自动重试。数值分类复用原有检测条件，未改变力场、步长、阈值、MDP、种子或研究定义。
- Decision 只读校验当前状态、授权、期限、事件头和证据引用；不执行提议、不连接模型。
- launch 持久登记避免重复 start；reconcile 仅进行数据库与既有回执对账，不运行 MD；无回执仍保留预留、要求人工审查。
- 证据审计纳入缺失快照／回执／启动日志、底层控制账本和全部声明任务，前后复核事件及文件清单。
- v1 Campaign 只读，不原地升级旧资产。使用方法见[指南](../guides/harness.md)。

## 本轮实际验证

| 项目 | 实际结果 |
|---|---|
| 全量单元回归 | 261 项通过，13.720 秒；较首版新增 28 项 harness 测试 |
| 普通实验 | 1 Run；首个准入子操作后请求暂停，分析尚未发生；显式恢复后完成，构建／输入未重写 |
| ZIL 数量研究 | 4 Run；同样验证子操作暂停、原批次恢复和最终证据闭包 |
| CAT/ANI 双构建研究 | 4 Run；第一次 NVT 实际中断，保留原 Run 并恢复完成 |
| 检查点实测 | 8912 原子，NVT 第 160/1000 步（0.32/2 ps）封存为 interrupted；原 Run `research-b4aa12039bd149e5ab87c61bd4d89a62` 最终完成 |
| 缺失检查点 | 仅复制该中断 Run 到测试专用副本，再删除副本 md.cpt；恢复在启动任何子进程前明确拒绝，原 Run 不受影响 |
| 完成与去重 | 3 Campaign 全部 completed，各 2 次有限投递；再次 run 未改变 work/operations；3 份审计 issues 均为空 |
| 实际产物 | 9 Run、36 个最终阶段封存、13 份分析；中断历史另保留，不替代最终封存 |
| 耗时／容量 | 222.6946 秒；210,531,048 字节，约 200.8 MiB（含缺检查点测试副本） |
| 预算／协议 | 串行 2 CPU 线程；总上限 1800 秒／2 GiB；EM 上限 5000 步、NVT/NPT 各 1000 步、生产 2000 步，未扩展原 smoke 协议 |
| 离线安装 | 现有 setuptools 80.9.0、wheel 0.48.0 构建，新临时环境仅装本项目 wheel；能力发现及 3 个预检与源码一致，1.7557 秒 |
| 身份检查 | 实际 MD 报告、安装报告和验收后核心源码身份一致 |

真实计算使用现有 macOS 分析环境，GROMACS 2026.3-Homebrew、Packmol 21.2.3；安装态未安装分析依赖、未另跑 MD。未下载参数、未新增第三方依赖、未改全局环境。

### 故障证据：明确区分真实进程与注入

| 故障窗口／规则 | 验证方式与结果 |
|---|---|
| 意图提交失败 | 注入 ENOSPC，未启动 worker，无虚假扣费 |
| 意图已提交、无回执 | 真实非 MD 子进程提交 intent 后 SIGKILL；对账保留预留，进入人工审查，不重投 |
| 回执已写、结算失败 | 注入 ENOSPC；回执保留，对账只结算一次，父用时未知按完整预留计费 |
| 未提交事务被杀 | 真实子进程事务内 SIGKILL；由 SQLite 恢复，无未提交状态重放 |
| 损坏数据库 | 测试副本损坏后拒绝恢复，字节保持不变，不截断或新建替代账本 |
| 活跃 worker | 真实非 MD 子进程持有 worker 锁；拒绝接管，没有向其他 PID 发送信号 |
| 超过停止宽限 | 真实非 MD、忽略 TERM 的受控子进程；缩短测试宽限后 SIGKILL 回收，不声称成功或产生检查点 |
| 双 start／控制竞态 | 启动登记避免重复创建监督器；取消优先于完成；相同管理请求幂等，旧序号／不同内容拒绝 |
| 预算／权限 | 剩余额度不随恢复重置；等待过期拒绝启动；日志计入容量；撤销阻止旧提议和下一子操作 |
| 证据闭包 | 缺快照／启动日志逐项列出、全部未启动任务保留；读期间变化拒绝一致性结论；伪造成功回执不能替代 Run |

这些测试文件为 [基础测试](../../tests/unit/test_harness.py)、[加固测试](../../tests/unit/test_harness_hardening.py)、[故障窗口测试](../../tests/unit/test_harness_fault_windows.py)。测试夹具不是科学数据，也不是物理断电认证。

## 原始证据位置

MD 与故障副本：`/private/tmp/materiasim-harness-hardening-20260917-01/`。

- `acceptance.json` SHA-256：`41ff15a658c663225046dd6269be9a506bca976a5fa5412254a94c2a6a556b6f`。
- `checkpoint-guards/interruption.json` SHA-256：`d1d8b97c2419496fd4f67f597918f556dd276f72e49bf55e61c2cfcc2c28944c`。
- `single/`、`zil/`、`mixed/` 保存各自冻结输入、事件、原 Run、分析和启动／操作日志；三个 `*-evidence.json` 保存只读审计结果。

安装验证：`/private/tmp/materiasim-harness-package-20260917-02/`。

- `acceptance.json` SHA-256：`48d4a329b93475cae42edead0e1e54980c4efcacc1638beafc998e9a36b874bb`。
- wheel SHA-256：`1370353491be2b6f69f0c0e9980a529b9684c4669cb2ef7ac1214978ed9ab1d7`。

临时目录不是长期备份；Git 不包含这些输出。没有清理历史 Run。测试删除只涉及新建缺检查点副本中的 md.cpt，原检查点完整保留。

## 来源与未验收边界

- 依据 [GROMACS 2026.3 mdrun 文档](https://manual.gromacs.org/documentation/2026.3/onlinehelp/gmx-mdrun.html)核查 `-cpi` 缺文件可能从头运行，因此本项目在调用前拒绝缺检查点；不是把“传了 -cpi”当成恢复证明。
- 依据 [SQLite 原子提交说明](https://www.sqlite.org/atomiccommit.html)核查事务及恢复语义；数据库和 journal 不手工清理，持久性依赖文件系统／硬件。本轮仅验证软件故障窗口，不代表实际断电、设备故障或主盘满盘测试。
- H2 尚需活动嵌套 MD 期间最外层 supervisor 强杀、主机重启／会话退出接管、受控文件系统真实满盘与落盘失败的组合验收。现有代码不保证孤儿进程自动清理，也没有 RAM／VRAM 硬配额。
- H3/H4 外部 agent 执行、凭据隔离、DeepSeek；H5 新材料；H6 Linux/GPU／长负载、自适应追加均未交付。
- `scientific_quality=not_assessed`：本轮遵循 simulation-research 的小量预算和 simulation-diagnostics 的现场保护，工程跑通不等于平衡、充分采样或模型科学有效。

重复验收工具仍为 [verify_harness](../../tests/acceptance/verify_harness.py) 与 [verify_harness_package](../../tests/acceptance/verify_harness_package.py)，中断辅助为 [harness_faults](../../tests/acceptance/harness_faults.py)。重复运行必须使用新的明确外部目录和获准预算，不复用旧输出。
