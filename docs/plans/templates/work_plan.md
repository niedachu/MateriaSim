# 计划写作模板

本文件是模板说明，不是待实施计划。复制时用真实主题、日期与唯一 doc_id，正文至少包含以下内容：

1. 目标、范围和不做什么；用户授权边界。
2. 实际基线：源码、相关知识、证据与缺口。
3. 具体文件／职责、实施步骤、必要依赖与风险。
4. 工作项及主状态，未确定材料或外部条件如何处理。
5. 验收：工程、科学资料、数值／采样、模型适用性各说明哪些适用。
6. 回退和数据保护；不用整体重置回退文档任务。
7. Knowledge Extraction：知识落点、保留历史、未决事项。

## 文档头示例

用三个短横线包围以下 JSON 对象；示例不能直接当活动计划提交。

```json
{
  "type": "work_plan", "status": "draft", "plan_kind": "implementation-plan",
  "owner": "MateriaSim", "module": "materiasim", "domain": "analysis",
  "created": "2026-09-16", "last_updated": "2026-09-16",
  "canonical": true, "doc_id": "materiasim.plan.analysis.example",
  "source_path": null, "supersedes": [], "superseded_by": [],
  "related_kb": [], "related_code": [], "rag_exclude": true,
  "scope": "真实范围", "implementation_status": "仅方案"
}
```

以[计划规则](../README.md)的状态枚举为准；完成计划不代表完成其他范围的验收。
