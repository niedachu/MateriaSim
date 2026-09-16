---
{
  "type": "knowledge",
  "doc_kind": "verification",
  "doc_id": "materiasim.kb.verification.numerical_protocol_checks",
  "title": "数值与系综验证的适用条件及输出",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "merz-shirts-2018",
    "physical-validation-guide",
    "physical-validation-data",
    "openff-interchange-export"
  ],
  "related_code": [
    "src/materiasim/engines/gromacs/mdp.py",
    "src/materiasim/specs/purpose.py"
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

# 数值与系综验证的适用条件及输出

## 检查算法行为，不是自动证明材料准确

Merz–Shirts 将数值与系综一致性检查和通常的代码正确性测试区分开；其积分器检查讨论特定积分误差标度，不是“能量稳定就能发表”。[原论文 Integrator validation](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0202764)

下表是 C0 设计路由，未运行这些检查，也未安装 physical_validation。

| 检查 | 对照设计与最低信息 | 不适用／不足的情况 |
|---|---|---|
| 导出语义／单点能量 | 同坐标与模型，核对单位、原子映射、边界、截断、分项能量约定 | 只比总能量可能掩盖分项抵消；不是模型对实验验证 |
| 步长／积分收敛 | 同模型、明确的守恒量定义、多个步长和可比轨迹长度 | 不把任意有温压耦合的总能量涨落套进 NVE 标度 |
| 动能分布 | 温度、正确自由度、动能序列、相关性处理 | 固定／约束自由度计算错误；仅均温正确不能证明分布正确 |
| 动能均分 | 分子／组分身份、质量、约束、位置与速度信息 | 缺速度不能靠位置差分冒充等价输入 |
| 系综一致性 | 相同 Hamiltonian 的相邻状态、能量及必要的体积等序列，足够分布重叠 | 单状态轨迹、无重叠或未平衡，不能直接得出通过 |

OpenFF 官方示例通过不同表示的单点能量比较检验转换；接入时应先统一设置，再解释偏差。[导出与检查示例](https://docs.openforcefield.org/en/latest/examples/openforcefield/openff-toolkit/using_smirnoff_in_amber_or_gromacs/export_with_interchange.html)

physical_validation 文档分别列出各检查及数据需求；不是每项都需要速度，也不是有一个 XTC 就具备全部输入。[用户指南](https://physical-validation.readthedocs.io/en/stable/userguide.html)、[SimulationData 契约](https://physical-validation.readthedocs.io/en/stable/simulation_data.html)

## 公式与单位审查

对适用的二阶辛积分器、足够光滑且数值误差受控的保守动力学，可检查能量波动随 \(\Delta t^2\) 的标度；这是条件性收敛检查，不应改写为“所有 MD 的能量漂移必须按该律”。约束、邻居表与截断误差需要单独考虑。[Merz–Shirts 积分验证](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0202764)

对满足经典正则系综二次动能条件的 \(f\) 个独立自由度：
\[
\mathbb{E}[K]=\frac f2 k_BT,\qquad
\operatorname{Var}(K)=\frac f2(k_BT)^2.
\]
若输入用 GROMACS 摩尔能量单位 kJ/mol，热能常数应采用对应单位的 \(R\)，不能把 SI 的单粒子 \(k_B\) 直接代入。这是单位换算，不是把原子数当摩尔数。自由度必须扣除实际独立约束和移除的整体自由度，并核对特殊虚拟位点／冻结组。[工具的数据与单位要求](https://physical-validation.readthedocs.io/en/stable/simulation_data.html)

均值检查、方差检查与完整分布检验不是一回事。p 值不是“模型正确概率”；通过数值检查也不能说明充分采样慢构象或力场适合目标材料。

## 接入前保存的输出契约

本地验证设计需预先列出：工具／引擎版本、输入拓扑与其依赖、实际 MDP、原子与分子映射、单位、自由度、每类序列的输出频率、阶段窗口、检查命令和失败报告位置。先估算存储和运行预算，再申请必要输出。

当前 [MDP 策略](../../../src/materiasim/engines/gromacs/mdp.py)关闭全精度位置／速度／力流；不能宣称现有全部 Run 能直接做分组均分检查。旧缺失数据标为缺失；为补数据而重跑需明确授权，不追写旧结果。未来解析器必须与实际 GROMACS 版本核对，不能只相信自动读取得到的自由度。

## 结果记录

按“通过／失败／未运行／不适用及理由”逐项登记，保存统计量、预设判据、样本窗口和限制；不要用一个总的 verified 标记。用途审查仍由[已有用途政策](../../../src/materiasim/specs/purpose.py)管理，本页不会生成 accepted 证据。模型准确性另走[四层证据](evidence_levels.md)。
