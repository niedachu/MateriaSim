# 可扩展框架第一版：本地交付验收

日期：2026-09-15。状态：**P4/P5/P6 本地框架范围通过；科学质量未评估**。

对应[框架方案第 20 节](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)。本轮接续既有源码改动，未提交/推送，未删除任何历史 Run；没有使用 PowerShell、安装第三方依赖或修改全局 Python。参数资产保持；用途批准夹具仅用于测试。

## 验收结果

| 检查 | 结果与范围 |
|---|---|
| 单元测试 | 193 项通过；此前 177 项，新增 16 项 |
| 真实框架回归 | 15 个 Mac CPU Run、56 个阶段，319.27 秒；报告采样 365,511,333 字节 |
| 发行包与安装态 | sdist→wheel→隔离安装→仓库外 validate/build/run/status，通过；另 1 个 Run、2 个阶段，4.35 秒 |
| 已安装包分析 | 复用现有分析环境、显式导入已安装 wheel 的代码，通过；原 Run 不变 |
| 合计真实计算 | 16 个 Run、58 个阶段；CPU 两线程、串行，无 GPU 或长协议 |
| 历史保护 | 上一批 14 个 Run、2,684 个文件核查前后相同；改变执行源码后的恢复被拒绝 |
| 科学输入保护 | 六个既有单实验的 inputs 和派生 MDP 与上一批相同 |
| 归档 | Run＋控制账本＋登记分析完成态导出；中文/空格新位置核验通过；故意损坏副本被拒绝 |

输出字节为报告结束时的采样值，不含后来添加的只读审计报告等文件，不是磁盘硬配额。基础框架套件限制 15 任务、1800 秒、1 GiB；安装套件额外限制 1 任务、600 秒、1 GiB；均远低于上限。既有 MD 每阶段≤2000 步；没有启动历史正式生产入口。

## 三块新增实现

- **用途与执行**：ExecutionProfile v3、冻结工具定位、非 smoke 显式采样及容量估算；purpose_policy v1 绑定物理设计、原生环境、三份 JSON 审核材料。production 要求 reviewed bundle 和明确模型来源/分辨率/组分角色，不能只改 purpose。本地声明不是认证签名。
- **存储与回收**：复制前计量、独立且不覆盖的副本、源/目标哈希核对；storage_contract=1 强制代次清单核验；每次分析有独立 operation 命名空间；最外层存活监督器拥有并清理原生进程组；归档只读可搬迁。
- **工具与交付**：tools 列真实读写入口，--json-envelope 为成功结果增加版本化外层；新 archive/verify-archive 使用显式新路径和预算。源码包与 wheel 不带模型/轨迹；核心源码身份与安装后身份一致，研究资产由外部独立输入提供。

单元测试包含：两种非 smoke 用途正例、engineering_only 生产拒绝、参数/数量/采样变更、审核文件损坏、目标环境/工具不一致、有限资源、MD 和 EM 显式采样、容量不足时目标尚未创建、不覆盖/非硬链接、源变化/符号链接拒绝、代次清单遗漏/损坏、分析命名空间、CLI 机器错误、真实隔离后代进程回收。已有 GPU、身份、账本、重复提交、恢复和失败保留测试继续通过。

## 真实工程与软件夹具

框架套件重新执行既有 14 个任务：6 个单实验、原研究恢复 2 个、双场景双分析恢复 4 个、无分析 2 个。恢复后所有阶段只成功编译一次。首个新研究 Run 的封存代数为 em=1、nvt=2、npt=1、prod=1；中断代与最终代均通过哈希核查，未使用硬链接共享可变输出。

额外的 model_validation Run 使用已有无水 ZIL 短协议，目的为软件用途分支验收。审核人、依据及局限均明确标记 SOFTWARE TEST；审查 JSON 写在独立输出目录，不进入 catalog。实际采样配置到达 EM/MD 的派生 MDP，分析报告保持 model_validation 用途。production 的通过分支仅用合成元数据单测；没有生产用途真实计算或科学批准。

## 可复跑入口与明确证据

从仓库根使用已有分析解释器：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m unittest discover -s tests -q

PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_framework_delivery --output /实际新的外部路径/框架验收

PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_package_delivery --output /实际新的外部路径/安装验收 \
  --build-python /已有匹配构建环境/bin/python
```

构建环境必须事先具备 pyproject.toml 所声明的 setuptools 80.9.0、wheel 0.48.0，以及可用于离线安装项目的 pip。脚本不下载依赖；没有该环境时明确停止。安装测试环境只安装本项目，分析补充检查使用现有 MDAnalysis 2.7.0、NumPy 1.26.4，而不是声称全新环境安装了 analysis extra。

本次实际证据根：

- `/Users/niezhidong/Desktop/MateriaSim-runs/framework-delivery-20260915-01/`：acceptance.json、regression/ 全部任务与 193 项测试日志、reviewed/ 软件夹具、storage/ 三份归档、historical-audit.json。
- `/Users/niezhidong/Desktop/MateriaSim-runs/package-delivery-20260915-01/`：acceptance.json、sdist/wheel/install 日志、installed-origin.stdout、independent-study/、runs/；analysis-extra-check/acceptance.json 是之后的安装态分析补充记录。原安装报告的 not_tested 不回写抹除，补充记录单独说明新增覆盖。

归档原 Run 为 `research-a45ea5796e4248ad9a4cd474b1fd110b`，导出与迁移副本的 archive_hash 均为 `3b8739aedea5146cb36c22a0ece90f214485d76155315116fce021427a8cab37`。`storage/corrupted-copy/` 是明确故意损坏的负例，不能作为备份使用；其他原始证据未改动。

本次复用此前 `/private/tmp/materiasim-bcd.vZ6vBJ/build-env/` 的已安装构建工具，未新增第三方依赖。临时虚拟环境和发行文件留在外部验收目录；Git 源码备份不等于这些科研证据的备份。

## 限制与后续

Linux/GPU 实机、长负载、大轨迹、真实模型科学审核、新材料/相态、远程调度未验收。GPU 仍是受限单 CUDA 候选；已有工程模型未升级。容量预检/巡检不是硬配额，独立副本可能昂贵。最外层监督器自身被 SIGKILL、掉电、恶意进程主动逃逸不属于本地进程组清理保证。

archive 是完成态证据的只读复制和本地完整性检查，不是活动 Run/批次重绑定、跨平台检查点续跑或整机灾备。旧未登记外部分析、Research 计划/比较/批次账本不由单 Run 归档自动发现。完整研究备份需另保留其整套资料。

本轮依照 [simulation-research 技能](../../skills/simulation-research/SKILL.md)执行有界短测并区分工程结果与科学结论；[agent-ask-plan](</Users/niezhidong/.codex/skills/agent-ask-plan/SKILL.md>)采用用户授权的 agent 执行模式。上述验收不评估 LLM 自主科研成功率。
