# Harness：监督器丢失与隔离卷满盘验收

日期：2026-09-17 启动，2026-09-18 完成最终核查（Asia/Shanghai）。承接[本地加固报告](2026-09-17__harness-local-hardening.md)，历史测试结果不改写。此次仅继续[方案 H2](../plans/2026-09-17__harness__plugin-research-automation__architecture-plan.md)；没有连接外部 agent、新增依赖或新材料，没有 commit/push。

## 修改与边界

核查发现父监督器被强杀后，原 worker 可以继续推进下一操作。新增 [SupervisorConnection](../../src/materiasim/harness/liveness.py)：监督器独占匿名管道写端，worker 仅继承读端；断连检测向自身发一次 SIGTERM，由已有嵌套运行器转发协作停止，下一 build/run/resume/analyze 准入再次同步拒绝断连。

实现只改变外层存活保护，不改变 GROMACS 模型、力场、数值参数、阶段步数、种子、容错或科学判据。管道不是 PID 文件，不向从磁盘读取的旧 PID 发信号。监视结束后关闭描述符，不在正常退出后继续发信号。

这是协作保护，不是 OS 服务／硬资源隔离：worker 卡死、父子同时被杀或机器关机时，不保证回执、检查点和孤儿回收。缺回执仍拒绝重投，已有回执通过规范结果核验后只结算一次。

## 实际结果

| 检查 | 结果 |
|---|---|
| 全量单测 | 267 项通过，14.203 秒；本轮新增 6 项管道／SQLite 故障测试 |
| 活动 MD 中强杀 supervisor | 父进程真实退出码 -9；worker 感知管道关闭，原 NVT 在 160/1000 步、0.32/2 ps 保存可核验中断；8912 原子 |
| 禁止下一投递 | 4 任务研究只创建第一个 Run，最后准入动作仍为 run，没有继续构建其他任务；审计无缺失项 |
| 对账 | 显式 reconcile 后 paused、无 active 操作；父层计时丢失，因此保守计入原完整预留 300 秒，没有退款／重置额度，也未继续该 Campaign |
| 整个 owned 进程组丢失 | 测试辅助仅通过实际保有的子进程句柄和归属组强杀，同时父层自杀；无回执，needs_human_review，原预留保持；再次请求运行未修改 work/operations |
| 启动客户端退出 | 启动 campaign start 的 CLI 实际退出；独立 supervisor 继续完成 1 个 ZIL Run，审计闭包通过 |
| MD 规模 | 共实际创建 3 个原配置 Run：1 个完成、1 个可核验中断、1 个故意强杀；不是 3 个全部完成的科学模拟 |
| MD 成本 | 串行 2 CPU 线程，38.9161 秒、34,946,914 字节（约 33.3 MiB）；低于 900 秒／1 GiB 约定上限 |
| 隔离卷满盘 | 新建独立 128 MiB HFS+ 映像，在不同 st_dev、受限容量的挂载点填充 130,691,072 字节后返回真实 errno=28（ENOSPC） |
| SQLite 满盘拒绝 | 管理 pause 返回 OperationalError：unable to open database file；没有成功响应，也没有提交事件。移除测试独有填充文件后对账，序号仍为 0；随后新的合法 pause 成功 |
| 满盘安全边界 | 没有启动 MD；只在测试映像填充，不在主盘创建无限文件；成功后正常卸载，映像与日志保留。不是实际断电或物理设备损坏测试 |
| 离线 wheel 检查 | 仅安装本项目 wheel，能力发现和 3 个 preflight 与源码一致；未下载第三方依赖、未另做安装态 MD；1.7480 秒 |
| 身份 | 进程验收、成功满盘验收、安装报告与验收后核心源码哈希一致 |

原 smoke 协议保持：EM 最多 5000 步、NVT/NPT 各 1000 步、生产 2000 步。两个故障 Run 在 NVT 被停止，没有偷偷改长协议。科学质量均为 not_assessed。

### 满盘测试的失败尝试也保留

1. `...disk-full-20260917-01`：受限环境中 hdiutil 返回“设备未配置”，未挂载。申请受控权限后重试。
2. `...disk-full-20260917-02`：映像可创建，但夹具把 Campaign 额度设成整个卷大小，忽略文件系统开销；实际预检正确拒绝。随后仅把测试声明额度纠正为 16 MiB，生产门禁不变。
3. `...disk-full-20260917-03`：64 KiB 填充写失败仍留下少量空闲块，小 SQLite 事务实际上成功，因此测试失败。没有删断言或把它冒充满盘拒绝；改为按文件系统块大小填充后在全新映像重验。
4. `...disk-full-20260917-04`：得到上述真实 ENOSPC 与拒绝写入结果，测试通过。

02／03／04 均正常卸载；失败映像不删除，03 内仍保留其测试填充文件。04 只删除新建的填充文件以释放测试卷空间，不涉及用户数据；该填充文件无科研内容，不作恢复保留。主盘累计保留约 3 × 128 MiB 测试映像及本轮运行日志，临时目录不是长期备份。

## 原始证据

本轮所有位置都在 `/private/tmp/`，不进 Git：

| 文件 | SHA-256 |
|---|---|
| `materiasim-harness-crashes-20260917-01/acceptance.json` | `e07e53667e68893f949ea7ba442aec6a3305f227b583bc42fcc241150ebf1558` |
| `materiasim-harness-disk-full-20260917-04/acceptance.json` | `9aed82edc97d9ce18559681531ebc5d66b50493f5f924a37e94a8dd988896ff7` |
| `materiasim-harness-package-20260917-03/acceptance.json` | `ae7a49d14b5cc6f262b300b301607372d7fd057c9514c72a1fce95020d326f9c` |

安装 wheel SHA-256：`f91bdd4a8828282560098f209d7af4786dca238874cef5f01253d41c701a9299`。成功中断 Run：`research-d7d7a7d442fd4b6ab5fe15e39915ccdf`。每个进程场景保留独立 Campaign 及 stdout/stderr；成功映像保存满盘恢复后的 Campaign，不手改数据库。

## 复验入口和资料核对

- [管道单测](../../tests/unit/test_harness_liveness.py)：EOF 启动拒绝、非管道拒绝、边界拒绝、实际子进程 SIGTERM、正常清理无信号、SQLite page limit 的真实 SQLITE_FULL。
- [进程验收](../../tests/acceptance/verify_harness_crashes.py)：`python -B -m tests.acceptance.verify_harness_crashes --output /新的外部目录`，必须使用已有分析环境、`PYTHONPATH=src` 和新输出目录，获得相应短测预算。
- [满盘验收](../../tests/acceptance/verify_harness_disk_full.py)：`python -B -m tests.acceptance.verify_harness_disk_full --output /新的外部目录`；仅 macOS、需要磁盘映像权限和至少 1 GiB 主盘余量。不得把挂载点替换成用户已有磁盘。
- 本轮核读本机 `hdiutil create -help`／`attach -help`；其 macOS 专用实现仅属验收工具，不给生产核心增加 Windows/PowerShell 路线。
- 已核对 [Python 3.9 Popen 文档](https://docs.python.org/3.9/library/subprocess.html#subprocess.Popen)中 pass_fds／close_fds 和独立会话语义，采用显式描述符传递，不使用线程不安全的 preexec_fn。
- GROMACS 恢复仍沿用核心输入／检查点核验，不仅传入 -cpi；对应 [2026.3 mdrun 文档](https://manual.gromacs.org/documentation/2026.3/onlinehelp/gmx-mdrun.html)。本轮原生停止行为的证据是实际日志和封存，不推断所有引擎都等价。

## 剩余工作

H2 本地功能与本轮明确的软件／文件系统故障矩阵已通过；实际主机重启、用户注销、断电／设备故障未做，不将“CLI 退出”写成“系统重启”。Linux/GPU、长负载和硬资源隔离仍须部署级验收。

H3 受限 agent 执行接口／真实宿主、H4 DeepSeek、H5 新材料、H6 服务器及自适应研究仍未交付；此次不借故障验收宣称整个方案完成。按 simulation-research 与 simulation-diagnostics 技能保留故障和负结果，不把工程验收转为科学适用性批准。
