---
{
  "type": "knowledge",
  "doc_kind": "verification",
  "doc_id": "materiasim.kb.verification.evidence_levels",
  "title": "四类验证与可追溯证据",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "平台证据分类与审查要求；不改变 purpose_policy",
  "source_refs": [],
  "related_code": [
    "src/materiasim/specs/purpose.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "local_definition",
    "implementation": "mapping_only",
    "evidence": "not_assessed",
    "applicability": "not_assessed"
  },
  "limitations": [
    "本轮为参考知识与代码映射审阅，不构成独立科学认证"
  ],
  "rag_exclude": false
}
---

# 四类验证与可追溯证据

## 分类是项目审查约定

| 层次 | 回答什么 | 证据示例 | 不能推导 |
|---|---|---|---|
| 工程贯通 | 文件、接口、执行、恢复是否正确 | 单元测试、受限真实工具短测、身份与输出核验 | 已平衡、模型可信 |
| 数值／物理质量 | 近似与目标算法行为是否合适 | 步长／精度对照、约束、适用的能量或系综检查 | 充分探索慢过程 |
| 采样质量 | 当前目标量有多少有效信息 | 窗口、相关性、重复、反证和不确定性 | 力场无系统偏差 |
| 模型适用性 | 材料、条件、性质是否有可靠验证 | 有来源实验／基准与完整方法、误差及适用范围 | 所有相态与性质都可靠 |

以上是为了审查而分层，不表示四层完全独立。正式结论须逐层说明已做、失败、未做和不适用，不用总的 verified=true。

## 最小证据记录

每个结论明确：研究问题、模型／输入哈希、代码与工具版本、平台、阶段／Run、观察量与单位、分析窗口、种子与重复、阈值及依据、原始产物定位、失败和限制。

新解释保存为新分析记录；历史 Run 和原始报告不回写。仅剩 Markdown 摘要时可以引用“历史报告声称”，不能声称重新核验了缺失原始文件。哈希说明内容完整性，不证明科学正确或身份认证。

## 用途边界

[用途政策](../../../src/materiasim/specs/purpose.py)对 model_validation 与 production 有不同证据角色要求，并核对目标及环境身份。现有 catalog 的 engineering_only 不自动晋升。

知识页的 source_checked/current 是本轮文档审阅状态，不生成 accepted 用途证据，不修改 purpose_policy，不授权运行。测试里的审核夹具也不是生产材料批准。

## 验收方式

实际入口和产物格式按[模拟指南](../../guides/simulation.md)；工程证据见[能力矩阵](../platform/capabilities.md)。本知识库首版只验收文档和相关定义检查，不新增任何四层中的真实 MD 证据。

新增研究的判断方法由[采样知识](sampling_uncertainty.md)、材料与模型资料共同确定；没有足够信息就报告缺口，不能用自动默认值替代科学判断。

## C0：预先设计验证，不预先批准模型

C0 交付的是[五类填写清单](../templates/specialized.md)，不是 Run、参数卡或 accepted 文件。按照下列顺序选基准：

| 对照层次 | 选择依据 | 不能替代 |
|---|---|---|
| 身份／解析／转换 | 可手算小例、固定几何、同模型分项能量 | 化学参数适用性 |
| 纯组分／简单子体系 | 同一温压、相态、化学状态下可信实验或高质量基准 | 所有交叉作用 |
| 成对组分／单界面 | 对目标交叉作用敏感的结构或性质 | 全混合物的竞争与协同 |
| 目标多组分场景 | 与研究问题相同的估计器和实验口径 | 条件外的泛化能力 |

基准卡至少记录 DOI／数据版本、来源可访问性、温压／组成／样品或计算方法、测量定义、参考误差、是否曾用于拟合、适用差异。参数拟合数据与独立验证数据必须区分；找不到匹配基准就把主张降为探索，不把近似相似材料当真值。

阈值在看正式结果前给出依据：科学上有意义的差异、参考不确定性、数值／统计预算。工程容差、统计区间和模型允许偏差是不同量；不设置适用于所有材料的固定百分比。每类验证分别用通过／失败／未运行／不适用记录，失败后保留旧结果和修改原因。

## C1—C4 的进入条件

本项目后续材料批次顺序是：C1 选体系并完成来源／参数审查 → C2 适配与工程／数值验证 → C3 采样及模型适用性验证 → C4 证据归档与有限范围回写。具体执行以[补充计划](../../plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)为准。没有选择体系和授权预算时，不进入真实计算阶段。

需要复审的触发项：

- 改端基、立构、质子化、交联或表面状态：重新核查化学身份、参数和受影响基准。
- 改力场／水／离子、交叉项、AA/CG 或结构偏置：重审模型定义与适用性。
- 改温压、浓度、几何、尺寸并超出验证范围：重审场景和采样／尺寸效应。
- 改引擎、导出器、硬件或精度：重做必要工程及[数值检查](numerical_protocol_checks.md)，不要求轨迹逐位一致。
- 改选择、窗口、归一化或统计方法：新分析记录，历史 Run 不回写。

以上是文档层审查要求，不是已实现的自动触发器；本轮不改用途政策或批准任何模型。
