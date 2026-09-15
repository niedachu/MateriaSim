# 编译阶段交接：Mac CPU 工程验收

日期：2026-09-15。状态：**本子批通过；框架方案未全部完成；科学质量未评估**。

对应[可扩展框架方案](../plans/2026-09-15__framework__extensible-core-v1__implementation-plan.md)第 16 节。延续用户“继续”的实施与小量验收授权，原备份提交为 e223731；本轮没有新增提交或 push。

## 本轮交付

- `engines/contracts.py` 新增 PreparedStage；`engines/prepared.py` 验证持久化交接与输入/编译产物身份。
- `engines/gromacs/compile.py` 负责真实 grompp、前驱状态选择、冻结原生查找树、有效派生 MDP 与编译产物。执行函数只消费准备结果，不自行编译。
- `workflows/execute.py` 使用同一适配器显式 prepare_stage → run_stage；准备耗时会扣减本次执行剩余时间，耗尽后不启动 mdrun。
- v2 阶段新增独立版本的 preparation 契约；旧记录不补写，现有原源码身份恢复检查保留。
- 原算法、力场、水模型、温压、步长、种子、模型源文件和已有协议模板未修改；没有新材料、依赖、GPU 后端或正式采样。

源码文件以上均相对于 `src/materiasim/`。初始 EM 编译产物仍参与构建映射校验；不宣称已经实现完整引擎无关模型或 Run v3。

## 测试与失败记录

使用已有分析解释器，从仓库根执行：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -q
```

- 改动前 112 项通过；本轮增加 12 项，最终 124 项通过。
- 新测试覆盖准备记录往返、禁止重复编译、目标/引擎变化、TPR 篡改、原生输入闭包增加、参数/格式冲突、编译期间输入改变、前驱完成与检查点身份、历史记录不补写、版本/路径拒绝、编译耗时扣减。
- 现有原生退出码测试只隔离验证信号解释；准备校验有独立负例和下方真实 GROMACS 证据，未把测试替身加入公开能力。
- 第一次新增测试运行有 8 项错误、1 项失败，原因是新夹具未将 macOS 临时路径 `/var/...` 规范为 `/private/var/...`；实际工作流已有路径规范化。修正夹具的 `.resolve()` 后重跑通过，未删除断言。

## 真实验收入口、预算与环境

执行入口是实际存在的受限验收工具；它会启动 MD，不是只读查询：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_component_boundaries \
  --output /Users/niezhidong/Desktop/MateriaSim-runs/prepared-stages-20260915-01
```

复用 macOS Python 3.9.25、GROMACS 2026.3-Homebrew、Packmol 21.2.3、MDAnalysis 2.7.0、NumPy 1.26.4，未安装或升级环境。CPU 2 线程、串行；每次单实验执行 180 秒，动态阶段沿用现有每段最多 2,000 步；整批含构建/分析预算 30 分钟，输出停止阈值 1 GiB，不是 OS 硬配额。

最终结果：status=passed、pending=[]，约 **163.17 秒、161,518,979 字节（154.04 MiB）**。输出大小是最终报告落盘前的采样值。输入依赖与源码身份在验收前后保持。

## 实际覆盖

| 示例 | Run ID | 检查 |
|---|---|---|
| packed_zil_water | packed_zil_water-4476ed77d78e4e7dbc52d7a401e5a15c | 自动装配、填水、4 阶段、独立接触计数 |
| packed_ions_water | packed_ions_water-be5085eb9f8d4b9f877a60457635394d | 离子副本、填水、4 阶段、独立接触计数 |
| packed_mixture_water | packed_mixture_water-f7616366d2574786a78af4ca1d3f2cb4 | ZIL/CAT/ANI 三组分水盒、4 阶段 |
| packed_zil_dry | packed_zil_dry-4c859beab8324e0799e3b4ef4a519194 | 无水周期盒、2 阶段；不是固体验收 |
| zil_smoke_v2 | zil_smoke_v2-d841a5c9886344c0b0cd3d89bc4780cf | 预建单溶质水盒、4 阶段、水化旧算法对照 |
| cat_ani_smoke | cat_ani_smoke-d75037e752f64c5c9b11b1e3a6d9b823 | 预建离子对水盒、4 阶段、水化旧算法对照 |

研究恢复另有 2 个 Run，每个 4 阶段。首个 NVT 在 240/1000 步、0.48 ps、8,901 原子时实际中断；恢复原 Run 到完整目标，使用 `-cpi` 和 `-append`。批次账本记录 build → run → resume → analyze，没有重复构建。

合计 **8 个 Run、30 个阶段**：逐个验证准备契约、原生角色与输入闭包，全部恰好一次成功 grompp。中断前后 NVT 的 preparation 和编译产物哈希相同。恢复时没有重新编译；所有 Run 最终完成，且对应当前源码身份。

分析沿用现有双路径对照：四个 packed 案例使用独立最小镜像循环核对逐帧接触计数，两个预建案例与原水化实现对照；源 Run 在分析前后不变。这里只证明实现与工程运行，不证明平衡、独立采样或物性正确。

## 历史与输入回归

另行只读检查上一轮 `framework-boundaries-20260915-01` 下的 8 个历史 Run：全部可读、全部文件哈希与清单保持；使用新源码执行均按 Implementation changed 拒绝，没有生成 attempt 或补写 preparation。

对六个相同示例比较上一轮和本轮：resolved spec 身份相同；冻结 inputs、各阶段派生 MDP、protocol_overrides.json 逐字节相同。各例比较文件数为 CAT/ANI 43、packed 离子 41、packed 三组分 43、无水 35、packed ZIL 水盒 39、预建 ZIL 39。不比较动态轨迹的逐位一致性，也不对旧 CAT/ANI 随机删水的重新构建作确定性保证。

## 证据与未完成项

证据根为 `/Users/niezhidong/Desktop/MateriaSim-runs/prepared-stages-20260915-01/`：

- `acceptance.json`：8 个 Run、准备审计、恢复输入不变、环境/源码及耗时大小。
- `unit.stderr` / `unit.stdout`：验收启动时 124 项测试记录。
- `runs/`、`checks/`：六例真实 Run 和独立分析/参考结果。
- `research_resume/interruption.json`：中断时 NVT 完整封存记录；`research_resume/acceptance.json`：恢复与批次比较结果。
- 每个 Run 的 `attempts/*/compile-*/command.json`、`stages/*/stage.json`：实际命令与准备契约。

仍未完成：Experiment/Run v3、完整通用组分/模型/协议/场景契约与构建规划、Research v2、多分析研究比较、统一 ExecutionProfile/CPU-GPU 策略、分层源码身份、完整存储保护、安装态整体交付。当前仍从源码验收，未安装 MateriaSim 到复用解释器。

Linux/GPU 没有相应环境实测；新材料和科学质量未评估。按 simulation-research 技能保留了明确预算、独立输出、输入身份和工程/科学证据边界，不把短测通过当成整份方案完成。
