---
{
  "type": "knowledge",
  "doc_kind": "model",
  "doc_id": "materiasim.kb.models.biomolecular_preparation",
  "title": "生物大分子前处理与参数覆盖",
  "status": "current",
  "canonical": true,
  "owner": "MateriaSim",
  "created": "2026-09-16",
  "last_updated": "2026-09-16",
  "scope": "B 批通用参考与 C0 设计；不提供生产参数，不证明材料或平台已验证",
  "source_refs": [
    "gmx-pdb2gmx-2025",
    "martinize2-basic",
    "martinize2-elastic"
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

# 生物大分子前处理与参数覆盖

## pdb2gmx 的职责不是发现任意化学参数

GROMACS 2025.0 的 pdb2gmx 根据力场数据库处理残基、加氢并生成拓扑；可以选择端基／部分质子化状态、处理链分离与合并。没有数据库支持的残基不会因写进 PDB 就获得可信参数。[官方 Description](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-pdb2gmx.html)

本地审查先回答“是哪一个化学体系”，再调用工具。自动选择只是软件行为，不是材料状态的证据。

| 对象 | 必须核对的身份与结构 | 不允许默认推断 |
|---|---|---|
| 蛋白／肽 | 序列、突变、缺失残基／原子、链与生物组装体、末端、二硫键、辅因子 | 缺失环可以任意补；晶体非对称单元必然是目标组装体 |
| 核酸 | 序列、链方向、配对与末端、修饰、离子及参数覆盖 | 蛋白残基库或同名原子足以覆盖 |
| 糖类／糖蛋白 | 单糖立体化学、异头构型、糖苷连接位点和分支、连接处参数 | 组成相同就是同一糖链 |
| 配体／金属中心 | 化学图、键级、价态、质子化；配位用键合或非键合模型的依据 | 仅凭空间距离生成通用金属配位力场 |
| 无序或多态体系 | 目标状态集合、结构来源及构象偏置 | 一张结构或 RMSD 平台能代表整体构象分布 |

后四类的材料特定参数选择仍需 C1 专题检索，不在本页推荐某套通用力场。

## 推荐的前处理审计顺序

1. 保存原始结构来源、版本与解析说明；区分实验、预测、手工重建。
2. 明确取舍多构象／替代位置、缺失区域、非目标组分；每项改变保留映射与理由。
3. 固定链连接、端基、质子化状态；pH 是选择依据之一，固定质子化不等于恒 pH 模拟。
4. 核对所选数据库覆盖全部残基和跨残基连接。未知类型作为明确缺口，不能删除它来让程序通过。
5. 核对生成前后原子、净电荷、链与特殊键；重排编号后重建选择和约束。
6. 用特定结构／构象基准设计验证，不把氢键几何自动判断当实验确认。

其中链处理、端基机制和原子重排是 pdb2gmx 的实际接口边界；具体参数名称须与选定力场及安装版手册一致。[同一官方文档](https://manual.gromacs.org/documentation/2025.0/onlinehelp/gmx-pdb2gmx.html)

## CG 分支必须另外审查

martinize2 的基本流程涉及结构输入和版本相关行为；弹性网络可按分子、链或指定区域限制连接。[基本用法](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/basic_usage.html)、[弹性网络](https://vermouth-martinize.readthedocs.io/en/latest/tutorials/elastic_networks.html)

本地推论：若研究跨域运动／链间解离，跨域或跨链弹性连接会改变所研究的自由度，必须先审查；不能把结构被网络维持当作无偏稳定性或折叠证据。详见[粗粒化边界](coarse_graining_and_transferability.md)。

## 项目接入和验证

现有 [参数导入](../../../src/materiasim/engines/gromacs/parameters.py)是受限显式 GAFF 路径，不能假设 pdb2gmx 的输出可直接导入。后续需核对函数形式、排除、特殊项与序号映射，做适当转换／单点检查，之后再做材料验证。本轮没有引入生物模型或修改导入器。
