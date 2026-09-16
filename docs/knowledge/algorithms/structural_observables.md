---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.structural_observables",
  "title": "RDF、MSD 与链构象",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "RDF、MSD、链构象参考；项目尚无这些分析适配",
  "source_refs": [
    "gmx-rdf",
    "gmx-msd",
    "gmx-gyrate",
    "gmx-polystat"
  ],
  "related_code": [
    "src/materiasim/analysis/registry.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans",
    "materiasim.plan.scientific_knowledge.materials_and_validation_bc"
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

# RDF、MSD 与链构象

## RDF：相对局部密度，不是简单距离直方图

对均匀体相、固定组成和体积、互不重叠的粒子集合，可用薄球壳近似说明
\[
g_{AB}(r)\approx
\frac{\langle n_{AB}(r,r+\Delta r)\rangle}
{N_A\rho_B\,4\pi r^2\Delta r}.
\]
这里 \(N_A\) 指 A 组粒子数（不是阿伏伽德罗常数），\(\rho_B=N_B/V\) 为数密度，\(g\) 无量纲。实际有限箱、变体积和选择规则须按工具定义核对，不能把此简式当作所有模式实现。

GROMACS rdf 的 exclusions 不改变其归一化因子；表面模式的箱体积归一化有特别限制。记录选原子还是分子中心、bin、归一化和参考密度。[rdf 官方说明](https://manual.gromacs.org/current/onlinehelp/gmx-rdf.html)

后续适配应验证均匀参考系统、排除／重叠选择及粒子数变化，不能把界面 RDF 按体相公式直接解释。

## MSD：从位移到扩散有条件

\[
{\rm MSD}(\tau)=\left\langle|\mathbf r(t+\tau)-\mathbf r(t)|^2\right\rangle,\qquad
D=\frac{1}{2d}\frac{d\,{\rm MSD}}{d\tau}.
\]

扩散关系适用于所选 \(d\) 维度的正常扩散线性区间；不能覆盖弹道、受限或反常扩散。MSD 单位为长度²，D 为长度²/时间。记录粒子／分子中心、跨时间周期连续性、漂移处理、时间原点、最大滞后和拟合窗口。

GROMACS msd 的拟合与误差估计依赖线性区间；长滞后样本少，分析也可能占用较多内存。[msd 官方说明](https://manual.gromacs.org/current/onlinehelp/gmx-msd.html)

本项目后续测试应区分静止、已知位移、跨边界轨迹与随机扩散估计；确定性位移测试只证明几何处理，不证明扩散估计无偏。

## 链构象：先定义链和权重

质量加权回转半径为
\[
R_g^2=\frac{\sum_i m_i|\mathbf r_i-\mathbf r_{\rm COM}|^2}{\sum_i m_i},
\quad \mathbf r_{\rm COM}=\frac{\sum_i m_i\mathbf r_i}{\sum_i m_i}.
\]

质量、几何或其他权重不可混淆。多链应先按链计算再按研究定义汇总；把所有链合起来求一个 Rg 会混入链间分布。GROMACS 新版 gyrate 的默认质量权重及轴分量定义见[官方说明](https://manual.gromacs.org/current/onlinehelp/gmx-gyrate.html)。端到端距离还需明确链端原子／单元，环链没有同样定义。

先恢复每条分子的跨周期完整性；平移／转动不应改变标量 Rg。两等质量点相距 L 时 Rg=L/2，可作为已知答案测试。本页没有实际运行上游分析。

## 项目状态与采样

当前[分析登记](../../../src/materiasim/analysis/registry.py)含两类接触和[整盒密度](bulk_density.md)，本页的 RDF／MSD／链构象均未接入。要开发的是角色／选择、参数校验、工具调用、单位和结果证据封装，不是再写一套通用 RDF 或 MSD 内核。

无论哪一观察量，都要说明[窗口、相关性、重复和误差](../verification/sampling_uncertainty.md)。Rg 暂时平稳不能证明聚合物慢松弛完成。

## 主链相关与持久长度不能混用工具口径

对有序的主链键向量 \(\mathbf b_i=\mathbf r_{i+1}-\mathbf r_i\)，可定义单位切向
\(\mathbf u_i=\mathbf b_i/|\mathbf b_i|\) 和相关量
\(C(s)=\langle\mathbf u_i\cdot\mathbf u_{i+s}\rangle\)。
零长度键、缺失连接和支化路径未定义时不能计算；必须记录链内平均、跨链权重及跨周期重建。

GROMACS polystat 的端到端量使用每分子选择中的首末原子；内部距离和持久长度另有选项。其持久长度按主链键数计，使用偶数键间隔的角余弦，并在对数相关值上插值到 \(1/e\)，不是默认输出以 nm 计的任意指数拟合结果。[官方 Description](https://manual.gromacs.org/current/onlinehelp/gmx-polystat.html)

本地验收设计：直链已知几何、整体平移／旋转、PBC 重建、不同选择顺序应分别测试；环链和支化链没有明确路径时应拒绝通用端到端定义。链分布不同，要声明按链等权还是按质量加权；不能把 \(\langle R_g\rangle\) 与 \(\sqrt{\langle R_g^2\rangle}\) 混成一个指标。

内部距离的场景用途见[聚合物场景](../scenarios/polymer_solutions_melts_networks.md)，界面统计另见[界面观察量](interfacial_observables.md)。本次没有执行这些测试或增加分析器。
