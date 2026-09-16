# 工作计划规则

本项目计划的唯一根是 `docs/plans/`。[INDEX](INDEX.md) 管导航，[MIGRATION_MAP](MIGRATION_MAP.md) 管来源／位置／替代；稳定知识回写[知识库](../knowledge/README.md)。

## 命名与位置

新增文件采用 `YYYY-MM-DD__<domain>__<short-topic>__<plan-kind>.md`，按职责需要建立子目录，不按状态分类，不创建空目录。首版盘点的六份文档保留路径；历史名称例外登记在迁移表。模板放 templates，不计入活动计划。

## 元数据

使用 JSON frontmatter（合法 YAML 1.2 子集）以便标准库校验；不添加 YAML 依赖。必需字段为 type/status/plan_kind/owner/module/domain/created/last_updated/canonical/doc_id/source_path/supersedes/superseded_by/related_kb/related_code/rag_exclude/scope/implementation_status。日期用 ISO 日期字符串，关系用稳定 doc_id，源码路径以仓库为基准。

- 状态：draft、active、blocked、completed、superseded、rejected、archived。
- kind：architecture-plan、implementation-plan、migration-plan、refactor-plan、cleanup-plan、research-plan、validation-plan、execution-guide、governance-plan。
- canonical 表示规范版本，不表示批准或实施；rag_exclude 默认 true，不把计划当当前事实。
- completed 按明确范围和验收决定；单独列未覆盖的材料、科学与硬件验收。

已有 doc_id 保持不变。修改文档不扩大原任务授权；不自动安装、计算或清理。不存在第二套任务系统，工作项主状态仍在所属计划。

## 实施与收口

按[模板](templates/work_plan.md)写目标、非目标、依据、工作项、验收与风险。实施后填写 Knowledge Extraction：稳定事实写到哪里、历史内容保留什么、后续问题由谁管理。来源冲突记录而不抹掉旧方案。

本次旧 CPU/GPU 方案“未实施”的历史措辞已加当前审计说明；较新框架覆盖其中一部分不代表全部交付。旧报告的测试数字保持其当时范围。

校验入口见[知识维护](../knowledge/governance/maintenance.md)；自动检查不能判定科学正确性。
