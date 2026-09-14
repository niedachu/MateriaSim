# GAFF2 + AM1-BCC 参数化

本目录只保存可追溯参数化输入、脚本和小型结果。量化计算的临时文件和软件环境安装在H盘Linux发行版中。

## 工具边界

- RDKit生成并筛选代表构象；
- AmberTools的 `antechamber` 使用AM1-BCC生成全分子电荷，并分配GAFF2原子类型；
- `parmchk2` 生成缺失参数类比文件；
- `tleap` 生成Amber `prmtop/inpcrd`；
- ParmEd负责Amber到GROMACS格式转换；
- OpenMM/ParmEd与GROMACS用于单点能量和力的交叉检查。

不自行实现AM1-BCC、GAFF2原子类型、拓扑格式转换或周期性距离算法。历史RESP诊断环境和结果继续保留，仅用于解释路线变更。

## 隔离环境

Psi4/PsiRESP和AmberTools放在两个环境中，降低复杂依赖冲突：

- `envs/resp-qm.yml`：Python 3.9、RDKit、Psi4 1.9.1、PsiRESP核心包0.4.2；
- `envs/amber-md.yml`：Python 3.10、AmberTools 24.8、ParmEd 4.3.1、OpenMM 8.6.0、MDAnalysis 2.9.0。

完整的conda `psiresp` 元包固定了 `Python < 3.10` 和 `h5py < 3.2`，与当前Psi4/Numpy组合冲突；
因此本项目使用同一官方发行版中的 `psiresp-base=0.4.2`，并显式安装RDKit、geomeTRIC和MolSSI QC组件。
RESP拟合算法没有重新实现。

Psi4 1.9.1还必须固定 `libint=2.9.0` 和 `libxc-c=7.0.0`。更高版本虽满足历史包元数据的范围，
但分别会造成 `libint2.so.2` 缺失和LibXC泛函表不兼容；这两个锁定已经过实际Psi4能量计算验证。

两个环境安装在H盘承载的WSL2发行版 `ZIL-Ubuntu24` 中：

```text
/opt/zil/micromamba/envs/zil-resp-qm
/opt/zil/micromamba/envs/zil-amber-md
```

实际解析后的完整软件版本仍须写入最终元数据；YAML只固定关键兼容边界。

## 接受标准

- 至少生成50个初始构象并选择5至10个代表构象；
- AM1-BCC序列化后总电荷绝对误差小于 `1e-4 e`；
- 任一原子电荷绝对值超过 `2.0 e` 时自动拒绝（这是保守异常值拦截，不代表低于阈值即可自动接受）；
- GAFF2原子类型完整；
- `parmchk2`结果逐项审核，不把生成成功等同于参数可靠；
- Amber和GROMACS原子数量、顺序、总电荷、键角二面角及1-4缩放一致；
- `gmx grompp -maxwarn 0`通过；
- 单点能量/力差异有记录并符合预先设定的数值容差。

## 当前AM1-BCC结果（已冻结为正式单重复生产输入）

`prepare_gaff2_am1bcc.py` 已用AmberTools 24.8完成全分子AM1-BCC、GAFF2、`parmchk2`、
`tleap`和ParmEd转换。原始MOL2因文本精度产生`-0.004 e`残差；脚本只在残差不超过
`0.01 e`时对39个原子施加相同微小修正，最终总电荷约`+1.7e-5 e`。原子电荷范围为
`-0.749430`至`+1.435903 e`，三个磺酸根氧保持等价。

4.5 nm纯水盒的0.5 ns内部smoke已经完成，未出现真实LINCS、NaN或崩溃；随后同一
4.5 nm、2957 TIP3P水体系完成了1 ns生产设置测试。Amber/OpenMM与GROMACS的真空单点
能量差为0.000466 kJ mol-1，力的相对RMS差为0.0131%；三个代表构象的GAFF2最小化后
咪唑鎓环平面性、improper几何和键长均通过预设阈值。经用户指定采用单重复4.5 nm协议后，
五个AM1-BCC文件已冻结到正式`topology/`；其SHA-256和接受范围写入
`results/acceptance/ACCEPTED.json`。此前RESP文件保存在
`topology/archive_pre_am1bcc_freeze_20260906/`，不用于生产。

## 历史RESP结果（已拒绝）

HF/6-31G*量化计算、5构象/15取向ESP和两阶段RESP均已完成，但全分子拟合得到
`-4.1386 e` 至 `+6.6531 e` 的原子电荷，39个原子中有14个超过 `|2.0 e|`。
提高网格密度、逐构象拟合、关闭对称约束及增强双曲约束均未消除异常；直接Psi4静电势与
PsiRESP读取结果在约 `1e-11` 的数值范围内一致。因此该结果被判定为全分子点电荷拟合病态，
不能作为GAFF2生产参数。

`topology/`中已经导出的文件仅是问题发现前生成的隔离诊断产物，未通过验收，不能用于MD。
这些RESP结果不会用于后续生产。正式验收只针对当前GAFF2 + AM1-BCC路线；在剩余门槛完成前，
项目不会创建 `results/acceptance/ACCEPTED.json`。
