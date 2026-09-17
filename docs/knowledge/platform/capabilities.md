---
{
  "type": "knowledge",
  "doc_kind": "contract",
  "doc_id": "materiasim.kb.platform.capabilities",
  "title": "平台能力与验证矩阵",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-18",
  "scope": "当前代码与历史工程证据的范围；非新平台验收",
  "source_refs": [],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py",
    "src/materiasim/engines/gromacs/mdp.py",
    "src/materiasim/engines/gromacs/device.py",
    "src/materiasim/analysis/registry.py",
    "src/materiasim/research/compare.py"
  ],
  "related_assets": [
    "catalog/interaction_bundles/packed_mixture_bundle.json"
  ],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "not_applicable",
    "implementation": "code_checked",
    "evidence": "not_assessed",
    "applicability": "not_applicable"
  },
  "limitations": [
    "本地文档规则或实现范围，不是材料验证结论"
  ],
  "rag_exclude": false
}
---

# 平台能力与验证矩阵

初始基线：备份提交 a044693；知识库首版未改模拟代码，见[首版验收](../../validation/2026-09-16__knowledge-work-plans-acceptance.md)。后续 C2 已新增整盒密度分析；下表分别列出新增检查与历史实测，不能混称本轮全部重跑。

| 能力 | 上游／组件 | 项目状态 | 核对依据与缺口 |
|---|---|---|---|
| 预建水体系、已有小分子按数量装配 | GROMACS、Packmol、已有模型 | 受限实现；Mac CPU 历史短测 | [原生场景绑定](../../../src/materiasim/engines/gromacs/specification.py)、[M3 记录](../../validation/2026-09-14__m3-packing-subset-acceptance.md) |
| 模型／包／协议资产 | catalog 与输入冻结 | 已实现；主要 engineering_only | [组合资产](../../../catalog/interaction_bundles/packed_mixture_bundle.json)、[兼容知识](../models/force_field_compatibility.md) |
| 最小化与动力学 | GROMACS steep/md | 已接入当前白名单 | [MDP 检查](../../../src/materiasim/engines/gromacs/mdp.py)，不代表所有上游算法开放 |
| 冻结、运行、恢复、预算、封存 | 共用平台控制层 | 本地框架已交付 | [本地验收](../../validation/2026-09-15__framework-local-delivery-acceptance.md)，长负载另验 |
| CUDA 单 GPU 卸载 | GROMACS GPU | 候选路径，未硬件验收 | [设备策略](../../../src/materiasim/engines/gromacs/device.py)、[框架方案](../../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)；Linux/GPU 待实测 |
| hydration_contacts | MDAnalysis＋项目计数 | 已接入、工程观察量 | [算法定义](../algorithms/contacts.md)、[登记](../../../src/materiasim/analysis/registry.py) |
| component_contacts | MDAnalysis＋项目计数 | 已接入、工程观察量 | [算法定义](../algorithms/contacts.md)、[登记](../../../src/materiasim/analysis/registry.py) |
| RDF、MSD、链构象分析 | GROMACS 上游工具 | 项目未接入 | [定义与接入边界](../algorithms/structural_observables.md) |
| mass_density：整盒密度／体积 | GROMACS energy | 已接入；Mac 真实 EDR 提取与单测 | [估计器](../algorithms/bulk_density.md)、[验收](../../validation/2026-09-16__density-analysis-acceptance.md)；无空间剖面、自动平衡或科学置信区间 |
| 平衡判定与科学区间估计 | 统计方法／候选 PyMBAR | 未封装 | [统计知识](../verification/sampling_uncertainty.md)、[比较实现](../../../src/materiasim/research/compare.py) |
| 混合溶剂、通用盐配方 | 参数与构建接入 | 未实现 | [组成定义](../foundations/units_composition.md)、[材料扩展主线](../../plans/2026-09-14__multicomponent-multiscenario__implementation-plan.md) |
| 聚合物、生物大分子、纳米材料、固相／界面 | 专属模型与构建路线 | 未形成受支持功能 | [场景决策](../scenarios/multicomponent_solutions.md)，不能用无水周期盒冒充 |
| 文献与知识检索 | Markdown、来源登记、文本搜索 | A 首版＋B 通用专题、C0 清单 | [知识索引](../INDEX.md)；没有自动 RAG、材料批准或新增模拟后端 |
| 本地规则 Campaign | 现有注册表依赖解析＋SQLite＋POSIX 监督 | CPU engineering_smoke，Mac 闭环和故障专项已实测 | [指南](../../guides/harness.md)、[9 Run 闭环](../../validation/2026-09-17__harness-local-hardening.md)、[进程／满盘专项](../../validation/2026-09-17__harness-crash-storage-acceptance.md)；安全子操作暂停、检查点续跑、证据审计及监督连接丢失保护；实际重启／注销／断电、Linux/GPU 和长负载仍待验 |
| 本地 agent 决策协议 | Campaign v3＋Decision v2＋现有执行核心 | 本地代码和脚本 provider 工程验收完成 | [接口指南](../../guides/harness-agent.md)、[5 Run／285 测试](../../validation/2026-09-18__harness-local-agent-acceptance.md)；受限摘要、逐操作许可、超时与人工接管，不含真实模型和 OS 隔离 |
| 真实模型／DeepSeek 与动态插件 | 候选宿主和能力接入 | 未接入／未验收 | [计划状态](../../plans/2026-09-17__harness__plugin-research-automation__architecture-plan.md)；本地结构化协议不等于模型自主研究或认证沙箱 |

## 使用规则

已登记接口、依赖可用、原生执行、硬件实测和科学适用性是不同层级。先找表中支持范围，再读真实配置和指南。源码变更时同步本表对应行；不因上游发布新版本自动扩大支持声明。

[框架交付报告](../../validation/2026-09-15__framework-local-delivery-acceptance.md)记载的 193 项测试、16 个 Mac CPU Run／58 个阶段只属于其历史范围；不得当成本轮新增验证。正式用途仍受[证据规则](../verification/evidence_levels.md)约束。
