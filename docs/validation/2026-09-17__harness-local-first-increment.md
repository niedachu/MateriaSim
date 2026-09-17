# Harness 本地规则首版：实现与验收

日期：2026-09-17。基线提交 `bee0d787c558f52a840f3c037812d1f2dc523d2e`，本轮改动未提交／推送；此记录不替代未来的 Git 状态。对应[方案](../plans/2026-09-17__harness__plugin-research-automation__architecture-plan.md) H0—H2 **部分落地**，不是全方案完成。

## 交付与范围

- 静态内置能力组合：实际注册表、显式白名单、任务配置哈希和源码身份；worker 再验证。
- Campaign 契约、精确目录用户授权、冻结快照、SQLite 事务事件、预算与本机后台监督。
- 只读预检／状态／证据，以及 create/run/start/pause/resume/cancel/revoke 管理入口。
- 单实验及两既有研究包复用同一核心，不修改模型、力场、MDP、种子或已有研究问题。
- 目标级暂停／恢复、终态重复提交、过期／撤销拒绝、不确定交接拒绝自动重投；无 agent 模型接口。

使用说明见[Harness 指南](../guides/harness.md)。受 `simulation-research` 技能约束，计算仅作明确预算内的工程验证，不把运行通过解释为材料适用性。

## 实际检查

| 检查 | 结果与边界 |
|---|---|
| 修改前回归 | 215 项 unittest 通过 |
| 修改后回归 | 233 项通过；新增 18 项 Harness 单测 |
| 普通实验 | 原 v3 ZIL 水盒 1 Run；后台启动、运行中请求暂停、目标完成后暂停、显式恢复，已有工作文件不重写 |
| ZIL 研究包 | 4 Run，全部完成并核查分析与声明任务 |
| CAT/ANI 研究包 | 预建／装填两场景，共 4 Run，双分析完成 |
| 全部真实计算 | 9 Run、36 个阶段封存、13 份分析报告；串行 2 CPU 线程，GROMACS 2026.3-Homebrew、Packmol 21.2.3 |
| 重复提交 | 三个完成态 Campaign 再 run，不新增或修改工作／操作证据 |
| 耗时与空间 | 221.6749 秒，204,261,600 字节（约 194.8 MiB）；低于 1800 秒／2 GiB 总验收限制 |
| 隔离安装 | 已有 setuptools 80.9.0、wheel 0.48.0 离线构建；新临时 venv 只安装本项目 wheel；实际从 site-packages 导入 |
| 安装态一致性 | 内置列表和三个 preflight 与仓库相同；普通实验使用复制到外部的冻结资产，不依赖原案例资产路径 |

单测包含未知／禁用／重复能力、配置／源码变化、授权过期／错目录／未知字段、准备包拒绝、冻结损坏、幂等和过期管理请求、撤销与终态、取消／完成竞态、事务回滚／哈希损坏、未知交接保留预留、worker 锁、缺底层证据拒绝成功回执、完整预留只结算一次、双监督器排斥、预算不足、原生工具身份变化、磁盘预检，以及一个真实**非 MD 的休眠进程**的取消／进程组清理。测试夹具不代表材料科学验证，也不是完整 SIGKILL／断电矩阵。

安装态本轮只测能力发现和预检，**没有在新 venv 安装分析依赖或另做安装态 MD**；真实 9 Run 使用现有分析环境。未下载新资料／参数，未新装第三方依赖，未改全局环境。

## 原始证据

本轮临时验收输出：`/private/tmp/materiasim-harness-acceptance-20260917-01/`。

- `acceptance.json` SHA-256：`198ff942a493ff123272b9aaa306cdc90b7957749978259a749bcc8a67c03575`。
- `single/`、`zil/`、`mixed/` 各自含 manifest、events.sqlite3、快照、原生 Run、分析、操作和启动日志。
- `single-evidence.json`、`zil-evidence.json`、`mixed-evidence.json` 保存本次只读清单；科学质量均为 `not_assessed`。
- manifest 身份依次为 `a972ad386620a6b554fa02f834fcca2ee8312660eb5adb124142aed7ddd6fba2`、`fd00a787bca3cb2c98684b4c6cc0bddb2c1b59899ec3f7f0e8e6ef9d10456083`、`b4b44409eade8f3f91d442ed898a2afdf7240947578721e38aff3488ff33ef9b`。

隔离安装输出：`/private/tmp/materiasim-harness-package-20260917-01/`。

- `acceptance.json` SHA-256：`4936e0003d0128cf16219400492d58c692132706980b6ddf95c69eb1ae88503c`。
- wheel SHA-256：`e767f237dce16df3a8d260cb4a6bceb8521ff5089f8ef8ae70569c7b128d38c6`；报告保存全部 Python 源码哈希与安装路径。

临时目录不是永久备份，Git 不包含这些运行输出；本轮没有迁移、删除或归档用户历史结果。

## 重复验收入口

从仓库根、使用已有分析解释器；输出必须改成新的外部目录。后两条分别启动 9 个受限短任务、以及仅本地打包安装检查，不能不经授权自动重复。

```sh
PYTHONPATH=src python -B -m unittest discover -s tests -q
PYTHONPATH=src python -B -m tests.acceptance.verify_harness --output /新的外部目录
PYTHONPATH=src python -B -m tests.acceptance.verify_harness_package --output /新的打包目录 --build-python /已有匹配构建环境/bin/python --single-campaign /上述验收目录/single
```

## 未完成／未验证

- H0 统一错误分类／完整 Decision 契约；H1 通用依赖环、冲突与动态提供方未实现，动态扩展默认不可用。
- 暂停粒度仍为整个目标；完整研究中断恢复、孤儿进程协调、各持久化窗口、真实满盘／断电、强杀／嵌套停机等故障注入待补。
- 证据清单尚无完整缺失项审计，失败／未启动只有库存与状态；启动日志保留在 launches，但尚未纳入文件哈希清单。读取期间状态版本核对、完整便携导出待补。
- 本地授权不是密码学身份或隔离；无外部模型、凭据白名单、DeepSeek 宿主接入。
- Linux/GPU、长负载、任意材料／聚合物／纳米材料、科学收敛和模型适用性未验收。

因此结论是：**已有体系的本地规则首版真实跑通；H0—H2 尚需收口，H3—H6 未实施。**
