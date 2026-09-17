# H3 本地 agent 协议验收

日期：2026-09-18（Asia/Shanghai，原始 UTC 时间在 2026-09-17）。本记录只针对本轮本地受控决策接口，不修改历史验收，不代表真实 LLM／DeepSeek 已接入。

## 修改范围

- 新 Campaign v3 显式冻结 agent policy；默认规则 v2 保留，历史 v1 只读。
- Decision v2 准入绑定摘要访问回执、事件头、期限与用户权限；旧 Decision v1 仍只读。
- allowlist 摘要与脱敏 CLI 错误，不向 agent 返回原始日志、结构／轨迹、环境或管理证据。
- 一次 continue 仅放行一个 build/run/resume/analyze；不复制数值运行器，不改变科学输入。
- 失联等待／期限、人工接管／交回、幂等、竞争提交、活动不确定性保护；等待期遗留启动登记可持锁对账。
- 没有新增依赖、在线模型、下载、全局环境改动或 Git 写操作。临时安装只安装本项目 wheel，不下载依赖。

## 单元与回归测试

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -q
```

285 项通过（原 267＋本轮 18）。新测试见 [test_harness_agent.py](../../tests/unit/test_harness_agent.py)：显式 opt-in、未知／越权策略、恶意日志隔离、原路径错误脱敏、重复／竞争提交、单操作边界、伪造或过时视图、工作变化、过期许可、协议／JSON 长度、人工接管、未结算故障、撤销、终态不可重开、访问／决策限额、事务失败回滚、等待登记对账。

## 真实本机小量执行

工具：[verify_harness_agent.py](../../tests/acceptance/verify_harness_agent.py)。独立进程通过真正 CLI 读取／提交，provider 只执行确定性测试策略，无模型、SDK 或网络调用。

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m tests.acceptance.verify_harness_agent --output /private/tmp/materiasim-harness-agent-20260918-01
```

| 用例 | 实测结果 |
|---|---|
| provider 不响应 | 1 秒等待后 needs_human_review；0 操作、0 计费，不启动 MD |
| 单实验 | 1 个 Run 完成；3 个核心操作；3 次 agent 决策（含请求人工审查）＋1 次人工放行，人工控制后显式交回 |
| ZIL 数量研究包 | 4 个 Run 完成；12 次 continue 对应 12 个核心操作；全部声明任务均在审计中 |
| 每个边界重复提交 | 返回同一接收回执，未生成重复许可／操作 |
| 两次决策间没有 provider | 工作目录和操作文件保持不变，监督器未自行推进 |
| 最终证据 | 两个完成 Campaign 均无 issues，closure=completed_tasks_verified；质量仍 not_assessed |

既有 4.5 nm 水盒、ZIL/TIP3P、装填／速度种子及协议全部不变。EM 最多 5000 步，NVT/NPT/prod 为 1000/1000/2000 步；2 线程、串行，总授权上限 1200 秒／1 GiB。实际 **146.69381575 秒，106,230,388 bytes（约 101 MiB）**；单实验计费 22.944090291 秒，研究批次 105.894702126 秒。等待和客户端调用耗时不等于操作计费。

原始证据位于 `/private/tmp/materiasim-harness-agent-20260918-01/`：acceptance.json 保存完整源码身份，single-evidence.json／research-evidence.json 保存全部事件与任务；Campaign 各自保留原生 Run、分析、回执和账本。临时路径不是长期备份，未自动复制／清理。

## 隔离安装态

[verify_harness_package.py](../../tests/acceptance/verify_harness_package.py) 使用既有构建环境，离线构建并只安装 MateriaSim wheel；不装分析／原生工具依赖，不重复 MD。

输出 `/private/tmp/materiasim-harness-agent-package-20260918-01/acceptance.json`：passed。验证安装路径确实来自新环境、整包源码哈希相同、内置注册表与三个预检一致；4 个新命令在安装态存在，且 tools 将它们准确列为写操作。

## 不能从这些测试推出的结论

H3 本地代码＋脚本接口验收已完成；**真实 agent／LLM 的规划能力、提示注入抵抗评测、实际宿主权限隔离、凭据保护尚未验收**。恶意日志测试证明该摘要接口不披露其文本，不是对任意模型或任意 shell agent 的安全认证。

本机账户标签不是认证，哈希不是签名，transport=local 不是防火墙。同账户不可信任意写程序不在安全保证内。真实主机重启／注销／断电、Linux/GPU、长负载、动态插件、Campaign 便携导出、新材料与科学验证仍待分别完成；本轮未重跑旧 9 Run 或真实满盘故障专项，只通过回归测试保留其代码契约。

按照 simulation-research 技能固定输入、资源与工程结论；本轮没有模拟失败需要修改物理参数。没有把工程完成提升为模型验证或生产用途批准。
