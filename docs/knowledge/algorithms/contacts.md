---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.contacts",
  "title": "水化接触与组分接触",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "当前两类接触估计器；不等同结合热力学",
  "source_refs": [
    "mda-distances"
  ],
  "related_code": [
    "src/materiasim/analysis/component_contacts.py",
    "src/materiasim/analysis/hydration.py",
    "src/materiasim/research/compare.py"
  ],
  "related_assets": [],
  "related_plans": [
    "materiasim.plan.docs_governance.scientific_knowledge_and_work_plans"
  ],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
    "implementation": "code_checked",
    "evidence": "not_assessed",
    "applicability": "not_assessed"
  },
  "limitations": [
    "本轮为参考知识与代码映射审阅，不构成独立科学认证"
  ],
  "rag_exclude": false
}
---

# 水化接触与组分接触

## 定义与选择

这是项目现有算法的规范解释，不是通用水化层定义。对帧 \(t\)，组分选择集合为 \(A,B\)，分子身份为 \(m(i)\)，阈值 \(r_c\)：

\[
\mathcal C_t=\{\{m(i),m(j)\}:i\in A,j\in B,m(i)\ne m(j),
d_{\rm PBC}(i,j)\le r_c\},\quad C_t=|\mathcal C_t|.
\]

无序分子对只算一次，同分子内接触排除。水化的第 \(s\) 个位点组则定义水氧集合
\[
W_{s,t}=\{w:\exists i\in S_s,\ d_{\rm PBC}(i,w)\le r_{c,s}\}.
\]
每组计 \(|W_{s,t}|\)，union 计 \(|\bigcup_s W_{s,t}|\)，不是各组数量直接相加。

计数无量纲，但结果语义分别是 molecule_pairs 和 water_molecules；二者不能当成同一个观察量比较。

## 实现交接

- [component_contacts.py](../../../src/materiasim/analysis/component_contacts.py)使用 capped_distance，再按冻结 molecule_id 去重。
- [hydration.py](../../../src/materiasim/analysis/hydration.py)使用 distance_array；要求每个 SOL 分子选一个氧，且完整覆盖水。
- 阈值配置是 nm，距离计算前乘以 10 转为 Å；周期盒来自每帧。API 语义依据 [MDAnalysis 2.7 距离文档](https://docs.mdanalysis.org/2.7.0/documentation_pages/lib/distances.html)。
- 原子数、顺序、选择、坐标／盒有效性和时间递增必须通过检查；不能通过换选择偷偷解释缺原子轨迹。

算法步骤为：核对身份 → 逐帧计算周期距离 → 构建集合去重 → 写逐帧计数 → 汇总。报告自身不是原始轨迹的替代物。

## 当前统计到底是什么

水化报告给出
\[
\bar C=F^{-1}\sum_t C_t,\quad
s_{\rm pop}=\sqrt{F^{-1}\sum_t C_t^2-\bar C^2},
\]
其中 \(F\) 为读取帧数。源码有防浮点负方差的零截断；它不是均值标准误。组分接触报告给直方图和均值。两者均没有自动剔除平衡段，有效独立样本与置信区间均未评估。

当前按帧等权；严格递增不等于等间隔。若输入时间不等间隔，均值不自动成为时间加权均值。跨研究汇总见[比较实现](../../../src/materiasim/research/compare.py)，不能把 mean_of_run_means 当成已有统计置信区间。

## 可核查例子和证据

| 已有测试 | 检验的定义 |
|---|---|
| [水化测试](../../../tests/unit/test_analysis.py) | 周期跨边界接触、多个位点共享一个水的并集去重 |
| [装配／分子对测试](../../../tests/unit/test_packing.py) | 四个原子对只算一个分子对；同组选择排除内部接触与对称重复 |

阈值附近还需考虑坐标精度与距离舍入；用稍低／稍高于阈值的例子区分容差问题。已有工程例子不证明某个阈值对真实材料合理。

接触阈值改变即改变观察量。计数随组成与数量变化，不能由计数直接推出吸附平衡、结合自由能、驻留时间或实验结合水。正式推断需另建定义、采样与[误差评估](../verification/sampling_uncertainty.md)。
