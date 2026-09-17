# 本地 Campaign 使用指南

这是 Harness 的**受限本地实现**，不是整份[架构方案](../plans/2026-09-17__harness__plugin-research-automation__architecture-plan.md)验收完成声明。只接受现有 `engineering_smoke`、CPU、固定实验／研究定义；不接 LLM、DeepSeek、远程服务器，不生成新材料或修改科学参数。本文主要介绍默认规则 v2；显式 agent policy 创建的 v3 见[本地 agent 指南](harness-agent.md)。

## 分层与能力

研究包／普通实验＋自动化侧车＋用户授权 → Campaign 冻结、监督和预算 → 现有 research/workflows/runtime → Packmol/GROMACS → Run／AnalysisRun。

[内置能力解析](../../src/materiasim/plugins/builtin.py)直接读取现有引擎、场景、构建器和分析注册表，不复制运行实现。白名单、任务选择、解析后配置哈希和整包源码身份一起冻结；worker 启动时再验证。禁用必需能力、未知／重复 ID、配置或实现变化都会拒绝。

当前是**静态内置能力组合**，不是可安装任意代码的动态插件系统。依赖图按真实注册表和原生场景绑定解析，拒绝缺依赖、循环、版本不支持和单任务内冲突；跨场景研究可以为不同任务选择不同构建器。创建时冻结所需分析依赖版本，worker 再核验，不自动安装或替换依赖。原生模型、场景、边界和用途检查照旧执行，注册能力不等于科学兼容。

## 只读预检

使用已安装的 MateriaSim，或从仓库根在已有环境中执行 `PYTHONPATH=src python -B -m materiasim`。不自动安装依赖。

```sh
materiasim campaign plugins
materiasim campaign preflight studies/zil_count_smoke/automation.json
materiasim campaign preflight studies/mixed_builders_smoke/automation.json
```

预检不调用原生工具、不联网、不创建输出；`environment=not_checked`。缺少真实定义的准备包直接拒绝。两个研究包已附侧车，普通实验使用同一契约：

```json
{
  "contract_version": 1,
  "id": "single_smoke",
  "target": {"kind": "experiment", "path": "experiment.json"},
  "capabilities": ["engine:gromacs", "scenario:packed_liquid", "builder:gromacs_packmol", "analyzer:component_contacts"],
  "allow_resume": true
}
```

`target.path` 相对侧车解析，也可为绝对路径；实验仍须是真实、完整且通过原校验的输入。侧车拒绝未知键，没有任意命令、Python 导入或物理参数覆盖字段。

## 用户授权与冻结

用户批准预算后，在独立文件中填写授权。以下路径和日期仅为格式示例，必须改成自己的真实路径和仍有效的期限，不自动续期。

```json
{
  "contract_version": 1,
  "subject": "zil_count_smoke_rules",
  "actor": "local-user",
  "output_root": "/private/tmp/my-zil-campaign",
  "expires_utc": "2026-09-18T12:00:00+08:00",
  "allowed_actions": ["execute", "resume"],
  "total_seconds": 600,
  "storage_bytes": 536870912
}
```

这是本机单用户的可追溯声明，**不是签名认证、多租户隔离或防恶意 agent 的沙箱**。`subject` 等于侧车 ID；输出根与命令精确一致；不能编辑旧 manifest 扩权。

```sh
materiasim campaign create studies/zil_count_smoke/automation.json --authorization /实际路径/authorization.json --output /private/tmp/my-zil-campaign
```

`create` 查询 GROMACS／所需 Packmol 的版本和二进制哈希，复制冻结资产，但**不启动 MD**。输出必须尚不存在，父目录已存在；不得位于源码／输入目录，不允许路径含符号链接。macOS 使用真实 `/private/tmp`；Linux 使用自己的真实外部路径。长期证据另选稳定存储。

复制失败保留部分目录供检查，不删除、不重用；修正后选择新目录，不能把失败创建当成可运行 Campaign。

## 执行与控制

```sh
materiasim campaign start /private/tmp/my-zil-campaign
materiasim campaign status /private/tmp/my-zil-campaign
```

`start` 启动脱离当前交互会话的本机监督进程，返回启动记录，不代表完成。前台运行用 `campaign run`。已实测启动 CLI 退出后后台任务继续完成；这不等于实际用户注销或主机重启验收。后台仍依赖本机、原 Python 环境和磁盘，不是开机自动恢复的系统服务。

管理请求携带当前 `status.sequence` 和唯一请求 ID：

```sh
materiasim campaign pause /实际路径/Campaign --request-id pause-001 --expected-sequence 1
materiasim campaign resume /实际路径/Campaign --request-id resume-001 --expected-sequence 3
materiasim campaign start /实际路径/Campaign
```

序号仅为格式示例，应先读真实状态。同 ID 同请求可幂等重发；同 ID 不同请求或旧序号拒绝。`cancel`、`revoke` 参数形式相同。

| 控制／状态 | 首版精确含义 |
|---|---|
| pause | 不强停 MD；在 build/run/resume/analyze 安全子操作之间暂停；已经准入的操作可以完成，不承诺阶段内立即暂停 |
| paused → resume | 仅恢复为 ready，仍须 run/start；身份、期限、预算和核心恢复条件继续生效 |
| cancel / revoke | 活跃时先 cancelling；停止并确认 worker 退出后才 cancelled；撤销不可原地恢复 |
| completed | 工程任务及分析通过，scientific_quality 仍为 not_assessed |
| failed / budget_exhausted / cancelled | 终态，不可 resume 重开或重置预算 |
| needs_human_review | 缺回执／交接不确定；保留证据与预留，不盲目重投，不允许通用 resume 绕过 |

恢复前校验上次回执及工作目录的完整进度哈希；删除旧 Run／批次不能触发重建。已完成操作不重做，可核验的中断须显式恢复，并满足核心检查点与账本规则。默认新规则 Campaign 为 contract v2；显式 agent policy 为 v3。投递次数上限均为 `2 + 3 × 任务数`，不改变底层 attempt 限额或总预算，不无限重试。历史 v1 Campaign 仅只读，不原地升级。上表 resume 仅适用于 v2；v3 使用单独的人工决策入口。

### 只读决策校验

`campaign validate-decision <Campaign目录> <decision.json>` 只验证提议，始终返回 `executed=false`，**不会执行决策**。契约字段为 `contract_version=1`、`request_id`、`source`、`action`、`campaign_hash`、`expected_sequence`、`event_head`、`expires_utc`、`reason`、`evidence`。动作仅为 continue/pause/request_review/stop；证据为 1–16 个 `{path, sha256}`，路径限定 snapshot/work/operations。请求须引用当前静止状态和真实证据，并满足有效授权。source 是描述字段，不是身份认证；这还不是外部 agent 提交接口。

## 预算与崩溃语义

- `total_seconds` 是目标操作**墙钟累计**，30–3600 秒；90 秒预留给停止／收尾。余额不超过 90 秒就不启动。不是 CPU 核时；与内层账本包含计费，不相加。
- 授权期限另控制等待／暂停；等待不计操作用时，但过期不能投递。Run、Research 更小预算仍有效。
- 容量阈值 1 MiB–2 GiB，包含快照、事件、轨迹、分析和日志，保留 64 MiB 磁盘余量。采样监控不是硬配额，不限制 RAM／VRAM；大写入和停机宽限可能越过阈值。
- `events.sqlite3` 使用事务、FULL 同步、序号和哈希链；从已提交事件重放状态。输入／事件单项限 2 MiB，最多 4096 事件；哈希不是认证签名。
- 意图与预留先提交，再启动 worker。本机 POSIX 锁分别保护 supervisor 和 worker；不依据旧 PID 杀进程，不支持 NFS／多机接管／活动迁移。
- supervisor 崩溃后，活跃 worker 的锁阻止接管；无回执不假定“尚未启动”。匹配回执需核对底层结果，只结算一次；父层实耗未知则保守计入完整预留。
- supervisor 存活时，协作停止超过 90 秒后才对本次拥有的进程组强制回收；强杀不保证检查点。新增的 worker 管道监视在 supervisor 消失时请求 SIGTERM，并在下一核心操作准入前拒绝断连；不通过旧 PID 猜测存活或杀进程。真实 NVT 内强杀 supervisor 已实测安全中断，但这仍是协作保护，不是操作系统孤儿进程回收器；双方一起被强杀或 worker 卡死时不能保证收尾。
- 整包源码身份固定，任一核心源码变化会阻止旧 Campaign 新执行；只读状态不要求同版代码。不能重写哈希伪造兼容。

显式 `campaign reconcile <Campaign目录>` 可在取得监督器／worker 锁后，让 SQLite 自己处理未提交事务恢复，并核对既有回执；**不启动 MD**。无回执仍保留预留并进入人工审查，损坏数据库不手改、不截断。启动登记避免重复 start；无活动意图的遗留启动登记可持锁对账后通过事件清除，再 start；也可显式 run 取得监督权，不能靠删除文件恢复。

已加入真实进程 SIGKILL／未提交事务、注入写失败和独立 128 MiB 卷的真实 ENOSPC 检查。满盘时管理请求失败、未产生虚假事件；释放测试专属填充文件后对账保持原状态。SQLite 持久性仍取决于文件系统／硬件，不是实际断电或物理设备故障认证。事务行为依据 [SQLite 官方原子提交说明](https://www.sqlite.org/atomiccommit.html)；检查点缺失必须先拒绝，不能仅依赖 `-cpi`（见 [GROMACS mdrun 文档](https://manual.gromacs.org/documentation/2026.3/onlinehelp/gmx-mdrun.html)）。

监督器实耗丢失时，对账仍保守扣除完整预留。本轮 parent-loss 虽保存了中断检查点，但 Campaign 的 300 秒额度已全部计费，**不能因 paused 就宣称还能继续**。本轮没有清账或自动创建新 Campaign 来重置额度。

## 证据与未实现项

```sh
materiasim campaign evidence /实际路径/Campaign
```

只在无未结算操作的终态／暂停／人工审查状态读取。清单包含 manifest 身份、事件头与全部事件、冻结输入、工作文件、操作回执、启动日志及所有声明任务；快照缺失、回执不符、日志缺失和未结算底层账本均显式列入 issues。完成任务复核 Run／分析；失败和未启动保留其真实状态，不伪造成功。读取结束再次核对事件序号和文件清单，变化即拒绝返回一致性结论。仅所有声明任务完成且 issues 为空时标记 completed_tasks_verified；这不是防恶意同用户写入的原子文件系统快照。

保留整个 Campaign 的 `snapshot/`、`manifest.json`、`events.sqlite3`、`operations/`、`work/`、`launches/` 及底层 `.materiasim-operations/`。`evidence` 是只读审计，**不是便携导出**；单 Run `archive` 不能替代整批保留。

代码：[契约](../../src/materiasim/harness/contracts.py)、[冻结](../../src/materiasim/harness/snapshots.py)、[事件](../../src/materiasim/harness/journal.py)、[监督](../../src/materiasim/harness/supervisor.py)、[流程适配](../../src/materiasim/harness/operations.py)。真实验收工具：[verify_harness.py](../../tests/acceptance/verify_harness.py)。

本地故障覆盖与失败记录见[进程／存储专项](../validation/2026-09-17__harness-crash-storage-acceptance.md)。v3 已有本地结构化决策执行，见[agent 指南](harness-agent.md)；尚未交付或验收：真实模型／宿主接入、凭据隔离、DeepSeek 插件、动态提供方、实际重启／注销／断电、Campaign 便携导出、Linux/GPU／长负载、新材料科学验证。本地闭环不是自主科学研究。v3 的 waiting_for_agent 也允许无未结算操作的管理证据审计。
