---
{
  "type": "knowledge",
  "doc_kind": "scenario",
  "doc_id": "materiasim.kb.scenarios.interfaces_and_confined_systems",
  "title": "界面、限域与几何相关协议",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "gmx-mdp-2025",
    "gmx-density-2025",
    "gmx-pbc"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/specification.py",
    "src/materiasim/engines/gromacs/mdp.py"
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

# 界面、限域与几何相关协议

## 先画清实际周期复制，再选协议

| 几何 | 本地设计必须回答的问题 | 不能照搬的设置 |
|---|---|---|
| 全周期固液双界面 | 有几面、两侧是否等价、液层是否有体相区、基底是否重复接触 | 用单面面积归一化双面总吸附 |
| slab 加真空 | 真空方向与厚度、偶极／长程处理、镜像敏感性 | 把真空体积算进液体浓度或均匀压缩真空 |
| 液液界面 | 两相组成、分界面漂移、各自体相平台、互溶与分配的目标定义 | 把所有帧在固定 z 上直接平均而忽略界面移动 |
| 自由或支撑薄膜 | 膜厚、两面或基底、不等价边界、允许变形方向 | 把薄膜密度和整体含真空盒密度混为一谈 |
| 孔道／限域 | 孔径与可达体积定义、墙原子或连续墙、受限方向 | 直接用整体盒体积和三维体相扩散公式 |
| 颗粒分散 | 颗粒尺寸／表面、周期镜像距离、径向分析可达区域 | 用平板 z 分布代替曲面壳层分布 |
| 外加应变／流动 | 控制量、参考态、非平衡目标、耗散处理 | 把非平衡轨迹按平衡 NPT 解释 |

这些是任务输入和审查问题，不是当前已实现的场景枚举。

## 温压与长程处理的选择边界

GROMACS 2025.0 MDP 中 semiisotropic 将 xy 与 z 压强耦合分开；anisotropic 又有不同自由度。选择取决于材料和边界条件，不是“有界面就用半各向同性”。含真空或刚性基底时，应先说明物理上允许哪些盒自由度。[MDP 压强耦合选项](https://manual.gromacs.org/documentation/2025.0/user-guide/mdp-options.html#pcoupltype)

同一手册的 ewald-geometry=3dc 是对特定 slab 几何的三维求和修正，不能作为所有固液界面的默认选项。必须核对实际电荷分布、周期方向和间隔；本页不推荐通用真空倍数。[MDP 长程设置](https://manual.gromacs.org/documentation/2025.0/user-guide/mdp-options.html#ewald-geometry)

本地协议应分别说明：解除近接、松弛可动组分、保持／释放结构约束、生产采样的目的。约束释放不是强制步骤；如果基底固定就是模型假设，应在结论中保留它。

## 分析坐标也属于模型定义

密度曲线必须约定参考表面、漂移去除、法向、分箱和随盒变化的处理。GROMACS density 的居中和相对分箱选项有明确语义；平均盒长不等于每帧实际几何。[density 官方说明](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-density.html)

平板应核对每帧面积与有效液相体积；颗粒径向统计应核对球壳被周期盒或其他颗粒遮挡的情况。详见[界面观察量](../algorithms/interfacial_observables.md)。

## 验证与停止条件

- 无法唯一确定表面状态或交叉参数：停在模型审查，不试图通过调温压参数补救。
- 无足够体相参考区：不能据此报告“相对于体相”的表面过量；需改设计或明确有限体系定义。
- 盒尺寸／真空间隔变化显著影响目标量：保留敏感性证据，不能直接宣称无限尺寸结论。
- 曲线稳但事件不足／不同初态未交换：属于采样不足，不是已经达到吸附平衡。

这些是本地科学审查规则，阈值需研究预声明。当前 [三维正交盒绑定](../../../src/materiasim/engines/gromacs/specification.py)和 [MDP 白名单](../../../src/materiasim/engines/gromacs/mdp.py)没有开放上述通用界面协议；知识补齐不绕过校验。
