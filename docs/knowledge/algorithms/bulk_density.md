---
{
  "type": "knowledge",
  "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.bulk_density",
  "title": "整盒质量密度与体积：能量帧估计器",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "GROMACS 已保存 EDR 帧的整盒质量密度与体积；不是界面剖面或材料科学验证",
  "source_refs": ["gmx-energy-2026"],
  "related_code": [
    "src/materiasim/analysis/density.py",
    "src/materiasim/analysis/registry.py",
    "src/materiasim/workflows/analysis.py",
    "tests/unit/test_density.py",
    "tests/acceptance/verify_density.py"
  ],
  "related_assets": [],
  "related_plans": ["materiasim.plan.scientific_knowledge.materials_and_validation_bc"],
  "supersedes": [],
  "superseded_by": [],
  "review": {
    "theory": "source_checked",
    "implementation": "code_checked",
    "evidence": "engineering_tested",
    "applicability": "not_assessed"
  },
  "limitations": [
    "仅有合成已知答案和既有 ZIL 水盒能量文件的 Mac 原生提取检查；没有乙醇模型科学验证",
    "不计算置信区间、有效样本量、自动平衡截断、过量摩尔体积或空间密度剖面"
  ],
  "rag_exclude": false
}
---

# 整盒质量密度与体积

## 工具负责什么

GROMACS `energy` 从 EDR 提取原生 `Density` 和 `Volume`。MateriaSim 不根据 GRO 原子名猜质量，也不重写 EDR 二进制解析器；封装复制、限时调用、单位／序列检查与证据保存。此路径不依赖第三方 EDR 包或 TPR 解析器。

官方特别区分保存帧与能量累积器：EDR 可能保留比输出帧更密的步平均，原生终端统计可比 XVG 帧均值使用更多信息。本实现保存终端输出，但**指标只取 XVG 已保存帧的算术平均**，不把两者混称为同一估计量。`-dp` 增加文本输出精度，不恢复未保存的数据。[GROMACS energy 文档](https://manual.gromacs.org/current/onlinehelp/gmx-energy.html)

## 本地估计器与单位

对显式窗口内的等时间间隔帧，原生密度为 \(\rho_j\)，体积为 \(V_j\)：

\[
\bar\rho=\frac1F\sum_{j=1}^F\rho_j,\quad
\bar V=\frac1F\sum_{j=1}^F V_j,\quad
s_\rho=\sqrt{\frac{\sum_j(\rho_j-\bar\rho)^2}{F-1}}.
\]

时间 ps，密度 kg/m³，体积 nm³；密度的样本标准差同样是 kg/m³。\(s\) 是帧间波动，不是均值标准误或置信区间。\(\langle M/V\rangle\) 通常不同于 \(M/\langle V\rangle\)，不得为了贴近实验替换定义。这些为本地明确选定的离散统计约定。

本方法只报告模拟整盒量。含真空层、固体或颗粒时，整盒密度不是液相区域密度；界面分箱和表面过量另见[界面量](interfacial_observables.md)。NPT 密度稳定也不证明聚合物构象或混合过程已平衡。

## 已接入的请求

在支持 EDR 产物的已完成 dynamics 阶段使用 `mass_density`：

```json
{
  "id": "bulk_density",
  "kind": "mass_density",
  "stage_id": "prod",
  "config": {"gromacs_command": "gmx", "begin_ps": 0, "end_ps": 4}
}
```

此处 0–4 ps 只展示短测语法，不是生产窗口建议。`begin_ps`／`end_ps` 是 EDR 中的绝对时间，闭区间，必须落在实际首尾帧；不自动判断或删除平衡段。`gromacs_command` 显式定位分析工具，记录实际版本和可执行文件哈希；不要求与模拟同路径，也不因此允许换引擎恢复 MD。

- 输入仅为已封存 `energy/edr` 角色；缺失时报错，不从其他文件猜补。旧 v1 Run 不支持该角色。
- 复制输入到独立 AnalysisRun，再调用原生工具，单次提取上限 60 秒；受监督 profile 的总预算规则仍适用。
- 必须有两个以上有限、正值且严格递增、等间隔的帧；列顺序按图例识别；检查 ps、kg/m³、nm³。未知格式、截断、缺项、重复时间、错误单位都拒绝。
- 输出 `density_volume.csv`、原始 XVG、命令及日志，报告保存哈希。研究观察量为 `mean_density_kg_m3`／`kg/m^3` 和 `mean_volume_nm3`／`nm^3`。
- `scientific_quality=not_assessed`；标准误、独立样本数和置信区间为 null。统计充分性见[采样知识](../verification/sampling_uncertainty.md)。

## 证据与缺口

[本轮验收](../../validation/2026-09-16__density-analysis-acceptance.md)覆盖已知答案、错误输入、公共分析分发、研究结果校验及 Mac GROMACS 2026.3 实际提取。原子模型和 MD 协议未改；乙醇参数、指定整数配比构建、纯水端点、实验逐点数据、独立重复、统计区间、Linux/GPU 尚未因此完成。
