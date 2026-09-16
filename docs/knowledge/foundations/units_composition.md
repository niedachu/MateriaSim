---
{
  "type": "knowledge",
  "doc_kind": "foundation",
  "doc_id": "materiasim.kb.foundations.units_composition",
  "title": "单位、身份与组成",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "组成定义、单位换算与盐配方核对；不提供浓度配置接口",
  "source_refs": [
    "gmx-units",
    "gmx-genion"
  ],
  "related_code": [],
  "related_assets": [],
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
    "参考知识，经资料对照；非独立专家认证或材料适用性批准"
  ],
  "rag_exclude": false
}
---

# 单位、身份与组成

## 统一语义

GROMACS 常用 nm、ps、K、e、u；能量 kJ/mol，力 kJ/(mol·nm)，压力输出 bar。1 nm = 10 Å，1 ns = 1000 ps，1 kcal/mol = 4.184 kJ/mol。不能只转换坐标而忽略力常数的长度幂次。[官方单位表](https://manual.gromacs.org/current/reference-manual/definitions.html)

“数量”必须标明是原子、分子、链还是颗粒；一个聚合物单体重复单元不等于一条链。质量分数不等于分子数分数。

## 组成换算：定义与自算示例

设 \(N_i\) 是组分分子数，\(M_i\) 为每摩尔该分子的质量，\(V\) 是所声明的体积：

\[
x_i=\frac{N_i}{\sum_jN_j},\quad
w_i=\frac{N_iM_i}{\sum_jN_jM_j},\quad
c_i=\frac{N_i}{N_A V_{\rm L}},\quad
V_{\rm L}=10^{-24}V_{\rm nm^3}.
\]

\(x_i,w_i\) 无量纲；\(c_i\) 为 mol/L。上式由分数和摩尔浓度定义直接换算，不是软件拟合算法。分母是否含所有组分必须声明。\(N_A\) 为阿伏伽德罗常数，计算示例采用约 \(6.02214\times10^{23}\ {\rm mol^{-1}}\)，不据此修改引擎内部常数。

示例：5 nm 立方盒为 125 nm³，0.1 mol/L 对应约 7.53 个配方单位；选 8 个时初始配方浓度约 0.1063 mol/L。这只是整数化示范，不是推荐体系。记录请求值、实际整数、偏差和电荷，不能静默归一化。

NPT 的体积会变化；说明报告的是 \(\langle N/(N_A V)\rangle\) 还是 \(N/(N_A\langle V\rangle)\)，两者通常不完全相同。多孔、界面体系还要说明使用全盒体积还是可达体积。

## 加盐的工具边界

GROMACS genion 用单原子离子替换溶剂；其 conc 选项按输入 TPR 体积计算新增盐，已有离子不被扣除；neutral 会额外加入中和离子。多原子离子不能默认使用同一路线。[genion 说明及 Known Issues](https://manual.gromacs.org/current/onlinehelp/gmx-genion.html)

项目建议顺序：区分目标配方与中和需求 → 算整数和电荷 → 选择工具 → 核对实际坐标／拓扑数量 → 报告最终组成。不要把新增盐浓度直接当最终总盐浓度。

## 本地映射与检查

当前已有按整数数量装配，不等于已实现通用浓度／盐配方解析，见[能力矩阵](../platform/capabilities.md)。换算检查至少包括体积单位、分母范围、净电荷、整数偏差及 NPT 体积口径。本页不更改现有配置 schema。
