---
{
  "type": "knowledge",
  "doc_kind": "governance",
  "doc_id": "materiasim.kb.governance.maintenance",
  "title": "知识维护规则",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "知识维护、状态和来源治理；本地文档规则",
  "source_refs": [],
  "related_code": [],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "not_applicable",
    "implementation": "not_applicable",
    "evidence": "not_assessed",
    "applicability": "not_applicable"
  },
  "limitations": [
    "本地文档规则或实现范围，不是材料验证结论"
  ],
  "rag_exclude": false
}
---

# 知识维护规则

## 单一归属

主题按 foundations、algorithms、models、scenarios、platform、verification 组织，不按作者或完成状态分目录。页面名用稳定 snake_case；一项规范定义一个 doc_id。README 和 INDEX 只导航，指南管理操作步骤；计划与原始验收报告保留历史语境。

所有正式知识条目使用 JSON 格式的 frontmatter（JSON 是 YAML 1.2 子集），便于标准库完整解析对象和数组，不新增 YAML 依赖。头尾仍是 Markdown 的三个短横线。导航、模板与来源说明不伪装成科学条目。

## 元数据和审查

必需字段见[知识模板](../templates/knowledge.md)。status 为 draft/current/deprecated/superseded/archived；canonical 只声明规范归属。

review 的四维：theory 为 source_checked/local_definition/not_reviewed/not_applicable；implementation 为 mapping_only/code_checked/not_implemented/not_applicable；evidence 为 not_assessed/engineering_tested/scoped_evidence；applicability 为 not_assessed/scoped_evidence/not_applicable。必须用正文解释范围及不适用理由，不能仅放标签。

- current 参考页要求关键主张有已核查来源或明确本地定义，并写适用边界；不要求先实现上游算法。
- 科学条目的本次审阅是 Agent 对照资料和代码，不是独立专家认证。新增本地实测必须链接具体记录；不得用人工标签替代证据。
- 无来源的猜测保持 draft 或进入探索文档，不转为规范结论。
- rag_exclude=true 用于草稿／历史／计划；false 也不表示已有索引服务或可脱离范围引用。
- source_refs 引用[来源登记](../references/sources.json)的稳定 ID；related_code/assets 使用仓库相对路径，related_plans 和替代关系使用 doc_id。

## 更新流程

明确任务授权 → 搜索已有知识／代码／资产 → 查相应一手资料 → 更新唯一规范页 → 同步索引及相关指南指针 → 检查链接／元数据／定义 → 记录限制。资料冲突记录版本、位置和未决项，不能脑补。

修改算法行为才同时修改相关测试；纯文档不自动运行 MD。普通 Run 不回写知识和计划；正式回写只在获准的维护任务中进行。文献事实、模型预测、本地结果和研究假设必须分开。

## 计划回写与迁移

计划收口填写 Knowledge Extraction，列规范知识、历史保留和未决事项。迁移见[提取映射](migration_map.md)；旧文档路径和科学输入不自动删除。代码事实以代码为准，科学正确性以证据审查为准，两者矛盾要另立任务。

## 可重复检查

从仓库根使用已具标准库的 Python 执行：

```sh
python -B -m unittest discover -s tests/unit -p 'test_documentation.py' -v
```

该检查覆盖链接、JSON 文档头、ID、索引、来源和元数据关系；不验证外部网页永远在线、不证明公式正确或科学结果可信。科学内容还需人工核对量纲、假设与引用位置。测试不需要 MDAnalysis，也不启动 MD。

本规则是 MateriaSim 的已采用文档约定，不是外部科学算法，因此理论和材料适用性项可标不适用。
