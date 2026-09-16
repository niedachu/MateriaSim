# 乙醇基准准备：整盒密度分析验收

日期：2026-09-16。范围：**C2 分析接入子任务通过；乙醇＋水模拟、C1 参数审核及 C3 科学验证未完成。**

## 实现与科学边界

新增 [mass_density](../../src/materiasim/analysis/density.py)，经现有分析注册、私有输入快照、研究结果校验接入。GROMACS `energy` 提供密度和体积，项目处理单位、窗口、哈希及日志；[估计器](../knowledge/algorithms/bulk_density.md)为等间隔保存帧均值与样本 SD，不报告 CI/SE、自动平衡、区域密度或过量体积。

未改力场／MD 协议，未下载新参数或实验数据、安装依赖、启动新 MD、执行 Git 写操作。使用现有 Python 3.9 分析环境及 GROMACS 2026.3-Homebrew。没有 PowerShell。

## 单元与回归检查

- 新增 `tests/unit/test_density.py`：11 项通过，含已知答案、图例换序、错单位／缺列／NaN／负值、时间重复／不等距／缺窗口、错误配置、观察量注册、公共分发／输入保护／研究校验、结果损坏拒绝、中断保留失败。
- 全仓库 `PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B -m unittest discover -s tests -q`：**207 项通过**（约 4.4 秒），其中含当前 5 项文档校验。此前 193 项历史报告保持原状。
- 合成数据明确只是单元夹具，不进入 catalog，不创建模拟或材料批准证据。

## 真实原生提取

来源为历史工程 Run：

`/Users/niezhidong/Desktop/MateriaSim-runs/framework-delivery-20260915-01/regression/existing/runs/packed_zil_water-6e0e7a02fdc343839ee0b0f717794fc7`

仅分析 `prod` 的 0–4 ps、21 个能量帧，不启动 MD。单次原生调用限时 60 秒；最终验收流程约 0.224 秒。输出位于：

`/private/tmp/materiasim-density-acceptance-20260916-02/`

`acceptance.json` 指向完整 AnalysisRun。报告 SHA-256：`59b84ff71360deee75d48267ea880d6d36397ba7796649986cf2c3ee356a9840`。原 Run **153 个文件**前后哈希一致，未写入轨迹旁缓存。

保存帧均值为密度 996.9536481584821 kg/m³、体积 89.22805568150115 nm³。该输入恰好由原生工具报告使用 21 帧统计，其终端均值按显示精度为 996.954、89.2281，与本地计算一致；不能由此推断所有 EDR 累积器均值都等于帧均值。

这些数字属于既有 **ZIL 水盒工程轨迹**，不是乙醇—水预测、实验或科学验证。第一次输出 `...-01/` 为增加轴单位校验之前的真实检查，保留不覆盖；`...-02/` 对应最终含单位校验的分析代码。临时目录可能被系统清理，不应视为长期科研备份。

可复跑入口（使用明确的新输出目录，不覆盖上述证据）：

```sh
PYTHONPATH=src zwitterion_hydration_md/.venv-macos-analysis/bin/python -B \
  -m tests.acceptance.verify_density --run /实际已完成Run路径 \
  --output /实际新建外部目录 --stage prod --begin-ps 0 --end-ps 4 --gmx gmx
```

窗口必须匹配该 Run 的实际能量输出帧。旧 v1 Run 不支持 EDR 角色；缺 Density/Volume 的阶段明确失败。本次真实提取使用旧 profile v1 已完成 Run；新 profile 的预算控制没有另造大规模模拟验收。

## 未完成事项

乙醇参数和实验逐点数据尚未导入，混合模型未锁定，纯水端点及指定整数配比仍需构建适配。Linux/GPU、长轨迹、平衡采样和独立重复未验证。[B/C 方案 §16](../plans/2026-09-16__scientific_knowledge__materials-and-validation-bc__research-plan.md)继续管理这些工作。

本轮按 [simulation-research](../../skills/simulation-research/SKILL.md)保留工程／科学证据边界；按 [agent-ask-plan](</Users/niezhidong/.codex/skills/agent-ask-plan/SKILL.md>)的执行模式落实最小可测试改动。
