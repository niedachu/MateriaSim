# 乙醇—水基准：来源准备与候选审查

状态：**已取得候选参数和实验数据；不是可运行或已科学验证的研究包。** 当前没有 `research.json`、生产协议或用途批准，不能直接交给 research run。

## 已取得的资料

2026-09-16，经用户批准的小范围获取，保存于仓库外：

`/Users/niezhidong/Desktop/MateriaSim-data/ethanol-water-sources-20260916-01/`

| 文件 | 内容与身份 |
|---|---|
| `freesolv/mobley_2310185.gro`、`.top` | 乙醇单分子坐标／显式拓扑；原样提取，不改电荷或参数 |
| `freesolv/database.txt` | 乙醇 ID、SMILES `CCO`、名称交叉核对依据；不是混合密度参考 |
| `freesolv/README.md`、`LICENSE`、`LICENSE_code` | 参数来源、许可与上游限制 |
| `nist/j.jct.2007.05.004.json` | 一篇论文的 ThermoML 数据，保留原文数据结构 |
| `nist/license.html` | 获取时的 NIST 官方许可政策页面原文 |
| `manifest.json` | 固定上游提交、URL、获取时间、文件大小、SHA-256 和 Git blob 身份 |

FreeSolv 固定提交：`6c7d19b4b565537365ffd22006aa2cd4643200c6`。GROMACS 参数包为 831,301 字节，读取后只保存乙醇的两个成员，不落盘整个参数包，不解压其他分子。原始参数包 SHA-256 为 `8065721760e4f82576f3908d23bb913194807a35429629b052f4e18e65d86139`。

实际获取脚本传输 1,443,358 字节；保留来源文件 618,590 字节，含清单合计 623,326 字节（约 0.62 MB，不含文件系统块开销）。这不含此前只读定位／网页查阅流量。8 个来源文件逐一检查大小和 SHA-256 通过；5 个 FreeSolv 下载对象另检查预先核对的 Git blob 身份。没有下载完整仓库、溶剂化大包、轨迹、环境或论文 PDF。

## 参数核查：不能直接进入 catalog

上游说明这条路线为 GAFF／AM1-BCC，水化计算采用 TIP3P；所取 `gromacs.tar.gz` 是经 ParmEd／InterMol 从 AMBER 转出的文件，而不是 `gromacs_original.tar.gz` 的旧 acpype 转换版本。这个来源支持模型追溯，**不证明乙醇—水混合液密度准确**。[固定版本说明](https://github.com/MobleyLab/FreeSolv/blob/6c7d19b4b565537365ffd22006aa2cd4643200c6/README.md)

直接核读下载拓扑，并与现有 [parameters.py](../../src/materiasim/engines/gromacs/parameters.py)、[topology.py](../../src/materiasim/engines/gromacs/topology.py) 对照：

| 核对事实 | 当前接入缺口／后续处理 |
|---|---|
| 9 原子、总质量 46.068 u；8 条键、13 条角、12 对 1–4 项、16 条二面角记录 | 后续仍需化学连接与转换能量检查，条目计数不等于物理正确性 |
| 电荷按文件十进制数相加为 **−0.0001 e／分子** | 100 个分子会累积为 −0.01 e；先追查上游精度／原始参数，不静默均摊电荷、不添加反离子掩盖、不放宽门禁 |
| atomtypes 为 8 字段，含 bonding type；`ho` 的 sigma、epsilon 都为 0 | 现有 7 字段读取及 sigma>0 检查不适用，不能为过检查随手填正数 |
| 二面角使用 function 3（Ryckaert–Bellemans），有重复原子四元组 | 当前导入只支持 1／4；不得去重或悄悄转换，需保持原始势函数和 1–4 约定 |
| defaults 为 `1 2 yes 0.500000 0.833333` | 不等于当前固定 AMBER defaults 的完整数值表示；不能无记录替换比例系数 |
| GRO 使用高精度坐标 | 当前固定 8 字符切片读取实际报错；应支持格式或另生成有来源的转换副本，原件不动 |

GROMACS 官方将二面角 function 3 定义为 RB，相关 1–4 规则需随具体力场理解，不能看到 RB 就一律删除 pairs。[官方拓扑表及说明](https://manual.gromacs.org/current/reference-manual/topologies/topology-file-formats.html)

本轮没有修改上述导入器，没有下载或锁定配套水拓扑，没有创建 `reviewed` 模型。原子类型名称也不能用于把 GAFF 与已有 GAFF2 直接合并。

## 实验数据核查：保留原始口径和冲突

来源：Gonzalez、Calvar、Gomez、Dominguez，J. Chem. Thermodyn. 39 (2007) 1578–1588，DOI `10.1016/j.jct.2007.05.004`；本轮核读 NIST JSON 的化合物、数据集、变量、约束、数值和不确定性，**没有核读论文全文或 SI**。[NIST 条目](https://trc.nist.gov/ThermoML/10.1016/j.jct.2007.05.004.html)

- JSON SHA-256：`4719c84b7d855c457936408224879f8335712447c5731d8f108792f9e06c5914`。
- `nPureOrMixtureDataNumber=12` 为乙醇（compound 3）＋水（compound 1）的液相质量密度，单位 kg/m³；不要误选相邻的黏度数据集。
- 37 个点分布为 293.15 K：13 点，298.15 K：12 点，303.15 K：12 点，并非每个温度 37 点。
- 变量 2 是**水摩尔分数**；乙醇摩尔分数应为其补数，不是原变量本身。298.15 K 下没有水摩尔分数 0.4971 的记录，不插值补成“实测”。
- 在 298.15 K 的两个端点，纯乙醇密度 785.46 kg/m³，纯水 997.05 kg/m³；这些是来源数据，不是本项目模拟结果。
- **压力冲突保留**：摘要表述 0.1 MPa（100 kPa），JSON 数据集压力约束为 **101 kPa**。未对照全文解决前，不能静默将其统一为 1 bar 或 1 atm。
- 数据标记为编译者评估的不确定性；`nCombUncertLevOfConfid=95`，各点保存 `nCombExpandUncertValue`。例如上述端点分别为 0.47、0.13 kg/m³；它们不是 MD 标准差，也不能未经核查一律除以 2 当标准不确定度。

## 许可与保存边界

FreeSolv 提供 CC-BY-4.0 数据许可和 MIT 代码许可，同时注明上游第三方来源可能有额外限制；保留其全文和归属。本轮只作本地研究准备，没有向远端发布原始数据。[FreeSolv 许可说明](https://github.com/MobleyLab/FreeSolv/blob/6c7d19b4b565537365ffd22006aa2cd4643200c6/README.md#license)

NIST 官方说明 ThermoML 文件由出版社许可公开；同时提供 NIST 通用数据许可／署名政策。保留官方页面，不自行将全部第三方文章和附件标为 CC0。公开分发前仍需核查对应材料条款。[ThermoML 说明](https://www.nist.gov/mml/acmd/trc/thermoml/thermoml-archive)、[NIST 政策](https://www.nist.gov/open/license)

## 复现与检查

[prepare_sources.py](prepare_sources.py) 只使用标准库，读取上限约 1.82 MB／次，逐文件 20 秒 socket 超时，固定 Git 身份，不执行上游脚本；失败时保留已有文件，不自动重试或覆盖。网络调用仅在显式执行 main 时发生。

```sh
zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  studies/ethanol_water_benchmark/prepare_sources.py --output /明确的新仓库外目录

PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m unittest discover -s tests/unit -p test_ethanol_sources.py -v
```

测试有 8 项：固定内容身份、精准成员选择、重复／缺成员／链接拒绝、乙醇化学身份、网络读取上限、不覆盖已有目录、拒绝仓库内输出、完整清单和字节核对。原始下载资料不作为测试环境必需品；测试不联网、不运行 MD。

本轮全仓库 `unittest discover -s tests -q` 共 **215 项通过**（约 4.5 秒）。另复核 8 份来源文件哈希、研究说明中的 5 个本地链接、已有差异及 3 个新增文件的空白检查，均通过；没有进行 Linux 或 MD 数值验收。

下一步先处理参数精度、压力口径和上游模型依据，再确定导入适配与明确预算的短测；完整进度由 [B/C 方案](../../docs/plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md) 管理。本轮按 [simulation-research](../../skills/simulation-research/SKILL.md) 区分来源审查和模型验证，未安装依赖、使用 GPU、启动 MD 或 commit/push。
