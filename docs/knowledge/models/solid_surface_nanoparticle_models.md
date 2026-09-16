---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.solid_surface_nanoparticle_models",
  "title": "固体、表面与纳米颗粒模型身份",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "pymatgen-surface",
    "interface-models",
    "lammps-hybrid"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/parameters.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.scientific_knowledge.materials_and_validation_bc"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
    "implementation": "not_implemented",
    "evidence": "not_assessed",
    "applicability": "not_assessed"
  },
  "limitations": [
    "仅核读来源登记所列章节；未完成特定模型主文、SI、数据及参数文件的联合复核",
    "本页为参考与本地审查规则，不是独立专家认证或可执行配置"
  ],
  "rag_exclude": false
}
---

# 固体、表面与纳米颗粒模型身份

## 几何模型与相互作用模型是两个交付件

pymatgen 的 SlabGenerator 提供晶面、厚度、真空层和终止面相关结构构建；接口中的长度可能用 Å 或晶面层数表达，必须核对参数口径。[surface API](https://pymatgen.org/pymatgen.core.html#module-pymatgen.core.surface)

INTERFACE 维护者仓库列出特定材料和表面状态模型，可作为候选参数来源；本轮只核查仓库说明，没有审核下载包、全部许可与具体参数表。[维护者仓库](https://github.com/hendrikheinz/INTERFACE-force-field-and-surface-models)

因此，拿到结构并不意味着拿到相容力场；工具名称也不是特定资产的科学批准。

## 本地模型身份清单

| 层次 | 需要固定的选择 | 会改变问题的变化 |
|---|---|---|
| 体相 | 化学组成、晶型／无定形来源、晶胞、缺陷、原子单位 | 换晶型、密度或制备历史 |
| 表面 | 相对哪套晶胞的 Miller 指数、终止层、重构／羟基化、固定质子化、净电荷 | 同材料换晶面、表面酸碱状态 |
| 颗粒 | 形状、尺寸定义、暴露晶面、曲率、配体种类和覆盖度 | 同直径但形状或修饰不同 |
| 力学自由度 | 全柔性、部分限制或刚性；固定层与受限方向 | 固定基底不能代表自由晶体热涨落 |
| 相互作用 | 势函数与覆盖元素、边界及交叉项、电荷方案 | 从非反应固定电荷跨到多体／反应／极化模型 |
| 参考态 | 温压、组成、制备方法、外部场／电极条件 | 恒电荷与恒电势不是一个模型 |

所有选择都要能定位来源与资产哈希；固定质子化表面上写一个 pH 数字，并不会自动模拟表面酸碱平衡。

## 不用逐对表误审多体势

逐对相互作用表适合检查两体项缺失，但无法独立表示多体作用。LAMMPS 的 hybrid 文档明确限制不同子势自动混合，也说明任意删除多体模型内的某些对作用会改变更广泛的局域环境。[LAMMPS hybrid](https://docs.lammps.org/pair_hybrid.html)

本地推论：不能用“固体内部一个势、溶剂另一个势、交叉全用任意 LJ”作为普适兼容方案。先核实整个势能表达和交叉模型；引擎能接受输入不代表这个组合有物理依据。

## 由简到繁的验证设计

1. **身份与转换**：晶胞／表面原子、电荷、计量与单位核对；从 Å 到 nm 的转换记录在资产边界。
2. **体相基准**：在模型适用条件下选择晶格、密度、结构或相关性质；不能以体相通过替代表面通过。
3. **表面与溶剂基准**：与目标一致的终止状态、界面几何和作用；选择匹配的实验／计算参考。
4. **纳米尺度目标**：尺寸、曲率、修饰和有限尺寸敏感性；明确哪些条件未验证。

本轮不给通用晶格误差阈值，也不推荐未知许可／参数的下载包。若研究依赖反应、溶解、电荷转移或恒电势，先另立方法调研和开发范围。

## 项目状态

现有 [参数路径](../../../src/materiasim/engines/gromacs/parameters.py)不是上述固体势的通用导入器；没有新增 LAMMPS 后端、材料资产或表面构建器。后续场景决策见[界面与限域](../scenarios/interfaces_and_confined_systems.md)。
