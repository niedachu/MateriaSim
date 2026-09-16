---
{
  "type": "knowledge",
  "doc_kind": "scenario",
  "doc_id": "materiasim.kb.scenarios.multicomponent_solutions",
  "title": "多组分溶液与复杂体系路线",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "小分子溶液路线与复杂体系决策入口；复杂材料尚未接入",
  "source_refs": [
    "gmx-preparation",
    "gmx-genion"
  ],
  "related_code": [],
  "related_assets": [
    "examples/v3/packed_zil_water.json",
    "studies/mixed_builders_smoke/research.json"
  ],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
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

# 多组分溶液与复杂体系路线

## 通用的是交接结构，不是同一套步骤

先明确目标量、化学模型、组成和环境，再选择装配、协议与分析。GROMACS 官方准备指南允许因研究问题和模型物理改变或省略部分阶段。[体系准备](https://manual.gromacs.org/current/user-guide/system-preparation.html)

| 阶段 | 研究要决定 | 平台应核对 |
|---|---|---|
| 模型 | 各组分身份、参数与兼容证据 | 资产完整、版本、拓扑与坐标一致 |
| 组成与几何 | 数量／浓度口径、盒、区域和电荷 | 解析后整数、最终计数、原子映射 |
| 构建 | 预建还是装填，溶剂／离子加入顺序 | 工具输入输出、重叠、拓扑同步 |
| 松弛 | 初态、约束、温压／边界选择 | 完整协议、状态继承、退出标准 |
| 采样 | 慢观察量、重复、时长和预算 | 输出足够、失败保留、续跑身份 |
| 分析 | 估计器、选择、窗口和误差 | 语义可比、来源可追溯 |

## 当前小分子子集

现有 [packed ZIL 示例](../../../examples/v3/packed_zil_water.json)和[混合构建研究包](../../../studies/mixed_builders_smoke/research.json)是工程例子，不是生产配方。已支持的装配范围见[能力矩阵](../platform/capabilities.md)。

有 CAT/ANI 不表示已实现任意盐。genion 替换溶剂及新增／中和数量的特殊规则见[组成知识](../foundations/units_composition.md)及[上游说明](https://manual.gromacs.org/current/onlinehelp/gmx-genion.html)。混合溶剂还需参数、计量和构建接入。

## 复杂例子：聚合物＋颗粒＋小分子＋水盐

这是尚未实现的研究设计检查表，不是可运行配置：

1. 固定链的单体连接、链长、端基与序列；颗粒的晶型、尺寸、表面终止／修饰；小分子的化学状态。
2. 审查整套[跨组分相互作用](../models/force_field_compatibility.md)，不能只确认各自有拓扑。
3. 定义体相还是固液界面、空间区域、边界、配方和中和需求。
4. 接入相应材料构建器并核对化学连接、区域、计数及最终拓扑；装填本身不生成聚合反应或接枝键。
5. 根据模型设计松弛与采样，不把当前水盒协议视为通用模板。
6. 定义分组接触、分布、链构象或吸附量，并明确哪些不能由当前接触计数得到。

## 场景变化触发什么复核

- 单链→多链溶液：链身份、链间与链内量分开，组成与采样重新审查。
- 溶液→熔体：不再机械加水，目标密度／构象与制备路径重新确定。
- 体相→固相／界面：边界、可变形对象、压力方向、静电与分析区域重新确定。
- 表面修饰或端基变化：重新检查模型身份与适用范围，而不是仅改名称。

这些是下一阶段的设计要求，不是已验证材料结论。选定体系前可以完善知识；具体参数和模型批准必须等待来源与证据。

## 从目标配方到构建后账本

本地建议为每个配方保存两层：**意图**（浓度／质量比／环境）与**解析结果**（整数分子数、实际体积口径和实际浓度）。实施时按顺序：

1. 指定计量基准及溶剂占比的分母，明确是否包含溶质、反离子。
2. 冻结[溶剂／离子组合](../models/solvent_ion_models.md)，以整数计量和电荷约束求数量；记录取整偏差，无法兼顾时要求研究者选择优先约束。
3. 区分先装填各溶剂、后加水或预建混合液体；只选实际支持且适用的路线。
4. 加离子后重新核对被替换的溶剂、原子排序、拓扑分子表、总电荷和最终组成。
5. 平衡体积变化后报告实际组成口径；界面或孔道另声明是否使用可达液相体积。
6. 使用目标量定义的误差与有限尺寸敏感性判断偏差是否可接受，不因“数量符合整数”就视为符合实验条件。

这些是待实现的配方解析规则，不是现有配置能够自动完成的流程。聚合物分支见[单链／溶液／熔体／网络](polymer_solutions_melts_networks.md)，固液与限域分支见[界面](interfaces_and_confined_systems.md)，研究前用[验证模板](../templates/specialized.md)登记缺口。
