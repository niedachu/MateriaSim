# 本地 agent 决策接口

H3 本地协议复用[规则 Harness](harness.md)和 MD 核心，逐步推进固定任务。没有 LLM、网络客户端、DeepSeek、自动参数优化或新材料生成；脚本 provider 验收不等于真实模型验收。

## 权限和归属

用户管理端创建任务、授权和策略，启动监督器，负责暂停、撤销、对账、人工接管。agent 端只暴露 `agent-read` 与 `submit-decision`，**不得同时授予完整 CLI、任意 shell、原始目录或管理接口**。

这是单用户本地接口，`agent_id/source` 是审计标签，不是身份认证。同账户任意文件写权限仍可绕过接口。真实模型部署必须另配宿主 allowlist、文件／凭据／网络隔离。`transport=local` 表示实现不联网、不授权外发，不是 OS 防火墙，也不保证调用方不会自行联网。

| 内容 | 归属与语义 |
|---|---|
| automation、authorization、agent policy | 用户创建时固定；agent 不能扩预算或改科学输入 |
| Campaign v3 manifest | 冻结 agent 策略，不原地升级 v1/v2 |
| agent_view 事件 | 记录实际披露的结构化摘要及哈希 |
| Decision v2 | 引用摘要、事件头和序号；只有四种动作 |
| agent_decision / human_decision | 分开留痕；一次 continue 只放行一个核心操作 |
| 原 Run／AnalysisRun、worker 回执 | 仍拥有计算事实；决策理由不是科学证据 |

## 创建

按[主指南](harness.md)准备真实侧车与用户授权。分步执行要求 `allow_resume=true`，授权含 execute/resume。单独准备策略：

```json
{
  "contract_version": 1,
  "agent_id": "local-agent",
  "allowed_actions": ["continue", "pause", "request_review", "stop"],
  "decision_timeout_seconds": 60,
  "max_decisions": 16,
  "transport": "local",
  "readable_summaries": ["progress"]
}
```

等待超时 1–3600 秒，决策上限 1–128；动作须是上述非空子集。仅实现 progress 摘要，没有任意日志／路径读取。

```sh
materiasim campaign create studies/zil_count_smoke/automation.json --authorization /实际路径/authorization.json --agent-policy /实际路径/agent-policy.json --output /实际路径/新Campaign
materiasim campaign start /实际路径/新Campaign
```

创建后为 waiting_for_agent；监督器可以后台等待，但收到合法 continue 前不启动 MD。省略 agent-policy 仍创建默认规则 v2 Campaign。

## 读取与提交

```sh
materiasim --json-envelope campaign agent-read /实际路径/Campaign --source local-agent --request-id view-001
materiasim --json-envelope campaign submit-decision /实际路径/Campaign /实际路径/decision.json
```

`agent-read` **会写访问审计事件**。仅静止决策边界可读；活动操作和已放行待启动状态拒绝。摘要仅含状态、任务总数、操作／决策计数、额度、期限、最后操作类型和输入／工作哈希。结构、拓扑、轨迹、原始日志、任务路径、环境变量、任意错误和模型理由均不返回。CLI 错误统一脱敏，详细问题由管理端检查。

返回 summary、view_id、sha256、expected_sequence、event_head；用真实值构造合法 JSON：

```text
contract_version = 2
request_id = 本次唯一 ID
source = 冻结策略的 agent_id
action = continue | pause | request_review | stop
campaign_hash = summary.campaign_hash
expected_sequence = 返回序号
event_head = 返回事件头
expires_utc = 不晚于 summary.deadline 的有效带时区时间
reason = 1–1000 字符，仅记录，不执行其中指令
evidence = {"view_id": 返回 view_id, "sha256": 返回 sha256}
```

请求不超过 64 KiB。未知字段、重复 JSON 键、旧协议、错误主体、无效哈希、非有限数值、过期、旧事件头、伪造摘要或读取后工作变化均拒绝。新披露推进序号，旧请求不能继续使用。

接受返回 `submitted=true, executed=false`：只说明许可已提交，不代表计算已经开始或完成。已启动的监督器消费许可；没有监督器时需管理端 start/run。相同 ID／内容重发返回原接收回执，不生成第二份许可；同 ID 改内容拒绝。已接受但尚未执行的许可也会过期。

## 操作粒度、超时和接管

一次 continue 只允许一个 build、run、resume 或 analyze，封存进度后重新等待。一次 run 可以执行全部已冻结阶段，**不是每一步积分或每个 GROMACS 阶段都询问 agent**。已准入操作按既有预算完成，等待期限不在途中修改物理协议。

- pause → paused；request_review → needs_human_review；均需人工接管，agent 不得自恢复。
- stop → cancelled，不能原地重开；用户取消／撤销优先于 worker 返回。
- 客户端退出不产生自动决策。当前操作可收尾，随后等待；超时转人工审查。监督器未运行时，状态可能暂留 waiting，但过期提交仍拒绝；`campaign agent-tick` 可持久化超时，不启动计算。
- 等待不计操作墙钟；授权、累计预算、磁盘和底层 attempt 限制保持不变。决策上限用尽不能通过交还 agent 重置。

管理端用真实 status.sequence 接管：

```sh
materiasim campaign human-decision /实际路径/Campaign --action continue --request-id human-step-001 --expected-sequence 真实序号
materiasim campaign start /实际路径/Campaign
```

人工 continue 同样只放行一步，之后仍保持人工控制。明确交回：

```sh
materiasim campaign human-decision /实际路径/Campaign --action return_to_agent --request-id handback-001 --expected-sequence 真实序号
materiasim campaign start /实际路径/Campaign
```

v3 不接受旧 resume 绕过人工边界。未结算活动操作、无回执故障、失败／取消／额度终态不能通过 human-decision 清除。监督器丢失后先 reconcile：有回执核对，无回执保留预留；等待期遗留启动登记可持锁对账清除，不会启动 MD。

## 证据和限制

最多 `4 × max_decisions + 4` 次新摘要披露，重复读 ID 返回原视图；journal 总上限仍为 4096 事件。完整 campaign evidence 含原始路径和事件，仅供管理端，不能直接外发模型。Decision v1 的 validate-decision 仍是只读历史提议检查，不属于受限 agent 工具；执行只接受 Decision v2＋Campaign v3。

代码：[消息](../../src/materiasim/harness/agent_contracts.py)、[摘要](../../src/materiasim/harness/agent_views.py)、[准入与接管](../../src/materiasim/harness/agent_service.py)、[状态机](../../src/materiasim/harness/agent_state.py)。[本地验收工具](../../tests/acceptance/verify_harness_agent.py)不调用模型。真实模型、DeepSeek、OS 隔离、Linux/GPU、长负载及科学验证均需分别验收。
