# 知识条目模板

复制时只建立确有内容的页面，按主题命名。使用两个 `---` 包围 JSON 对象；以下对象是元数据字段示例，不是活动知识。

```json
{
  "type": "knowledge", "doc_kind": "algorithm",
  "doc_id": "materiasim.kb.algorithms.example", "title": "实际主题",
  "status": "draft", "canonical": true, "owner": "MateriaSim",
  "created": "2026-09-16", "last_updated": "2026-09-16",
  "scope": "明确对象和非目标", "source_refs": [],
  "related_code": [], "related_assets": [], "related_plans": [],
  "supersedes": [], "superseded_by": [],
  "review": {"theory": "not_reviewed", "implementation": "not_implemented",
             "evidence": "not_assessed", "applicability": "not_assessed"},
  "limitations": ["尚未审阅"], "rag_exclude": true
}
```

## 正文必须回答

1. 问题／目标量及不适用范围。
2. 物理与统计假设：分辨率、系综、边界、平稳性等。
3. 方程和估计器：变量、单位、近似和来源定位；不能只写函数名。
4. 离散实现／步骤：选择、归一化、时间和权重；非算法页解释决策依据。
5. 参数：来源、适用范围、调整影响，不给无依据通用值。
6. 边界情况与反例：空样本、周期跨越、有限尺寸、失败和冲突。
7. 上游／本地映射：真实代码、版本、输入输出与未实现部分。
8. 验证设计与已有证据分别列；没有实测就直说。
9. 来源、读取范围、未决问题及局限。

多结论用“结论—来源—范围—状态”表分别记录。纯理论允许没有代码；字段不适用必须解释。例子见[接触定义](../algorithms/contacts.md)，审查规则见[维护](../governance/maintenance.md)。
