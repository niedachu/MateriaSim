---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.periodic_nonbonded",
  "title": "周期边界与非键作用",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "正交周期盒的几何解释及长程作用边界",
  "source_refs": [
    "gmx-pbc",
    "gmx-pme"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py"
  ],
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

# 周期边界与非键作用

## 几何定义

对正交盒长度 \(L_\alpha\)，最小镜像位移可写为：

\[
\Delta r_\alpha^{\rm MIC}
=\Delta r_\alpha-L_\alpha\operatorname{round}(\Delta r_\alpha/L_\alpha).
\]

所有长度同单位。这是正交盒的表示，不可直接用于任意倾斜晶胞。半盒位置存在等距镜像，测试阈值时考虑浮点与并列边界。短程最小镜像不等于只计算一个盒子的全部电作用。[GROMACS 周期边界](https://manual.gromacs.org/current/reference-manual/algorithms/periodic-boundary-conditions.html)

## 长程作用为什么单独处理

Ewald 将周期静电分为实空间、倒空间和自能等修正；PME 使用网格处理倒空间部分。实空间截断、网格与精度设置共同控制近似误差，“用了 PME”不是无限精确，也不等于孤立真空模型。[长程静电说明](https://manual.gromacs.org/current/reference-manual/functions/long-range-electrostatics.html)

## 参数与检查

- 明确盒矢量和周期方向；对当前正交短程情形检查截断与最短盒长关系，同时遵守引擎限制。
- 保存实际非键方法、截断、精度和完整 MDP；不能把装填容差当成动力学截断。
- 接触分析用瞬时盒；链构象需恢复分子完整性；位移分析还需跨时间连续性。三者不是同一种“去周期”操作。
- 薄膜和固液界面不能自动继承均匀体相的边界及静电设置。改变几何必须重新审查模型和有限尺寸影响。

## 实现与证据

GROMACS 有一般周期处理；MateriaSim 当前[原生适配](../../../src/materiasim/engines/gromacs/specification.py)只接受正交三维周期盒。倾斜盒、非周期和表面专用静电路线不能从上游能力推断为已接入。

几何已知答案可检验坐标平移一个盒矢量后距离不变；静电数值验证则需受控精度对照，不能由几何测试代替。本页未进行新模拟或精度基准。
