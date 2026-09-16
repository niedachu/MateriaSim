---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.interfacial_observables",
  "title": "界面密度、表面过量与接触的区别",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "gmx-density-2025",
    "iupac-surface-excess",
    "mda-distances"
  ],
  "related_code": [
    "src/materiasim/analysis/registry.py"
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

# 界面密度、表面过量与接触的区别

## 同一轨迹可以回答不同问题，不能混用名称

| 观察量 | 必须定义 | 不能替代 |
|---|---|---|
| 几何接触／接触占有率 | 选择、距离、原子或分子计数、时间窗口 | 热力学吸附量、结合自由能 |
| 法向或径向分布 | 参考面／中心、分箱体积、PBC、权重 | 未经归一化的跨尺寸比较 |
| 表面过量 | 分界面、液相体积、体相浓度和面积 | 某距离内全部分子数 |
| 停留时间 | 状态定义、连续／允许重入、截尾、采样间隔 | 最长一次接触或单条短轨迹的“寿命” |
| 吸附自由能／PMF | 反应坐标、采样与重加权、标准态及几何修正 | 对接触频次随手取负对数 |

本页只明确前 3 类的可用定义。后 2 类需要独立方法文献和验收设计，本轮没有形成其估计器或数值结论。

## 本地候选估计器：平板分箱数密度

对已定义参考面的、完整横截面的平板分箱：
\[
\widehat{\rho_i}(k)=\frac{1}{F}\sum_{t=1}^{F}
\frac{N_{i,k}(t)}{A(t)\Delta z_k(t)}.
\]
\(N_{i,k}\) 是组分 \(i\) 在该箱的粒子数，\(A\) 单位 nm²，\(\Delta z\) 单位 nm，结果为 nm⁻³。粒子可选分子质心或指定原子，但要固定一种定义；质量密度应另对质量求和。分箱边界使用一致的半开区间，最后一箱的周期处理需测试。

这是本地拟议的“逐帧除体积再平均”定义，不宣称与任意工具默认输出相同，也不等于“平均计数除平均体积”。盒长变化时还须声明比较固定物理位置还是相对坐标。若只统计可达液相区域，应以相应几何体积替代整箱体积，并标明不是同一个估计器。

GROMACS density 支持居中和相对分箱；其输出坐标与盒涨落处理有特定约定，封装前应在固定盒及变化盒样例上分别对照。[官方 density 说明](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-density.html)

## 表面过量需要体相参考

IUPAC 将表面过量定义为实际量减去按指定分界面延拓体相参考得到的量。[IUPAC surface excess](https://goldbook.iupac.org/terms/view/S06171/plain)

在“组分不进入固体、液相参考定义明确”的限定条件下，用粒子数而非摩尔数写成：
\[
\Gamma_i=\frac{N_i-\rho_i^{\mathrm{bulk}}V_l}{A_s}.
\]
这里 \(V_l\) 和 \(N_i\) 属于同一个定义区域，\(A_s\) 是其对应总界面面积；\(\Gamma_i\) 单位为粒子/nm²。对两个等价平面，若统计两面总量，面积应为 \(2L_xL_y\)。不等价两面应分区或明确只报告总和。分界面选择、参考浓度与误差必须随结果保存；负值可表示相对参考的耗尽。

**负例**：在颗粒外固定距离内计数后直接除颗粒面积，不减体相参考，得到的是区域载量，不应标成表面过量。曲面、孔道或无体相平台时，需重新定义参考，不直接照搬平板公式。

## C0 分析验收设计

- 均匀数密度样例应恢复已知密度；改变箱宽应保持积分粒子数（统计噪声另计）。
- 跨 PBC 平移、整体漂移与参考面一起移动，不应改变相对分布。
- 平板双面对称样例用于核对面积因子；变盒样例区分两种平均方式。
- 使用小型可人工核算坐标做语义测试，再与选定版本上游工具对照。
- 真实轨迹使用[相关性与重复](../verification/sampling_uncertainty.md)评估误差；时间分箱不是独立重复。

这些都是未执行的界面验收设计。当前 [分析注册表](../../../src/materiasim/analysis/registry.py)含两类接触及[整盒密度](bulk_density.md)，但没有空间密度剖面、表面过量、停留时间或 PMF 请求；整盒量不等于本页界面量。
