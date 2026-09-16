---
{
  "type": "knowledge",
  "doc_kind": "verification",
  "doc_id": "materiasim.kb.verification.sampling_uncertainty",
  "title": "平衡、采样与不确定性",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "常规平稳轨迹的统计参考；不覆盖模型系统误差或增强采样通式",
  "source_refs": [
    "grossfield-uncertainty",
    "pymbar-timeseries"
  ],
  "related_code": [
    "src/materiasim/analysis/hydration.py",
    "src/materiasim/analysis/component_contacts.py",
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

# 平衡、采样与不确定性

## 分清三个问题

是否脱离初始松弛、是否探索了相关慢状态、目标量估计有多不确定，不是同一个问题。画面稳定、密度平稳或同一初态多个种子，都不足以自动证明充分采样。

对近似平稳、等间隔标量序列 \(x_t\)，以归一化自相关 \(\rho(k)\) 估计：
\[
g\approx1+2\sum_{k=1}^{K}\rho(k),\qquad
N_{\rm eff}\approx N/g,\qquad
{\rm SE}(\bar x)\approx s_x/\sqrt{N_{\rm eff}}.
\]
\(g,N_{\rm eff}\) 无量纲；SE 与 \(x\) 同单位。截断 K、平稳性及有限采样会影响估计。此式不是非平稳轨迹、所有负相关过程或所有增强采样数据的无条件公式。

依据 Grossfield 等主文 §7.3.1 Eqs.11–12；该文不研究力场系统误差。[原文](https://livecomsjournal.org/index.php/livecoms/article/download/v1i1e5067/913/2595)

## 工具与方法的边界

PyMBAR 4.0 的 detect_equilibration 通过最大化保留段的有效样本量进行启发式选择，返回起始索引而非物理时间。它只看输入序列，不能保证发现从未访问的慢状态；statistical_inefficiency 的实现将 g 限制为至少 1，这也是实现约定而非所有过程定理。[维护者文档](https://pymbar.readthedocs.io/en/4.0.0/timeseries.html)

MateriaSim 暂无这些统计封装，不把算法页作为已经实现的自动平衡检查。

## 本项目研究设计要求

1. 预先列快／慢观察量、平衡判断依据、样本窗口和停止条件；保存剔除区间及理由。
2. 在不同初态、重复、时间段之间检查结论是否敏感；记录未出现转换、趋势未消失等反证。
3. 区分帧间标准差、均值标准误和置信区间；区间须说明方法和假设，不对相关帧直接套独立样本公式。
4. 使用时间块时说明块长、块数和相关性；不要把块数命名为独立运行次数。重采样也必须保留相应相关结构。
5. 模型、条件、估计器相同且比较设计允许时才合并；不能为缩小区间丢掉失败重复或不利结果。

这是平台的证据报告要求，不是保证所有体系收敛的自动流程。有效样本量随观察量变化；估计再精确也不消除模型偏差。

## 当前证据与后续验收

[水化实现](../../../src/materiasim/analysis/hydration.py)、[组分实现](../../../src/materiasim/analysis/component_contacts.py)及[研究比较](../../../src/materiasim/research/compare.py)目前均未给出科学置信区间。

未来统计接入先用独立随机样本、已知相关序列、常数段和非平稳趋势验证适用性与失败报告；工具失效应明确返回未评估而非零误差。本页只形成方法设计，没有运行统计基准或新增 MD。

## C0：怎样安排统计检查

以下是本地设计步骤，不新增可执行统计功能：

1. 为每个主要观察量确定估计器、单位、所代表的总体和允许误差；探索性观察量另标，不事后挑最显著结果当预设目标。
2. 保存准备段与生产段边界；同时检查若干物理相关的快／慢量。自动截断的建议与人工理由均保留。
3. 对生产段估计相关尺度，改变合理窗口／块长检查结果是否敏感。没有足够长的稳定段时，不报告虚假精确区间。
4. 多条重复区分“同一初态不同速度”和“独立构建／不同构象起点”；它们检验的敏感性不同。
5. 比较条件差异时先声明是否配对、共享何种随机量；保留失败或未完成重复，不用不等长轨迹直接拼成独立样本。

对 \(B\) 个等长、近似独立的时间块，块均值为 \(y_b\)，可采用
\[
\operatorname{SE}(\bar y)=
\sqrt{\frac{\sum_{b=1}^{B}(y_b-\bar y)^2}{B(B-1)}}.
\]
这是块均值样本方差除以块数的结果，单位与原量一致。块长不足导致残余相关，块长过大导致块数过少，两者都削弱误差估计；不能只挑使误差最小的块长。Grossfield 等 §7.3.2 讨论这一方法及块大小敏感性。[原文](https://livecomsjournal.org/index.php/livecoms/article/download/v1i1e5067/913/2595)

置信区间还需选择适当的分布／重采样假设；非线性估计器应在每个重采样单位重新计算，不把任意帧当独立抽样单位。重复运行的层次与时间块层次要分开报告，不能把二者混为重复数。

### 最低报告字段

目标量和单位；原始帧数、保留时长、输出间隔；截断依据；相关／块方法和参数；独立重复数及初态来源；均值、区间方法与置信水平；窗口／块长敏感性；未采到的过程与失败。常数段或零次事件不自动意味着真实误差为零；它可能只表示没有足够信息。

如果预算耗尽而证据不足，结果状态是“采样不足／待追加”，不是自动降低判据后通过。与模型参考的比较还须单列参考数据的不确定性和模型偏差。
