# Community Experience Seed Dataset

## 定位

Phase 7.4 将 Hermes 整理并校验的社区装机经验作为“经验提示层”接入现有知识库。数据集用于补充装机空间、走线、风道和主观观感等官方说明书通常不会完整覆盖的风险提醒。

原始数据位于：

- `data_sources/community_experience/community_experience_seed.md`
- `data_sources/community_experience/community_experience_manifest.json`

导入过程只读取并复制种子 Markdown，不修改原始 Markdown 和 manifest，也不访问互联网。

## 与 official_manual_seed 的区别

| 属性 | official_manual_seed | community_experience |
| --- | --- | --- |
| 角色 | 官方说明书依据 | 社区经验提示 |
| 主要用途 | 产品规格、接口、安装要求等确定性依据 | 装机风险、空间避让、观感和实践提醒 |
| `verified` | 由官方种子 manifest 决定 | 始终为 `false` |
| 回答优先级 | 高 | 低，仅作补充 |
| 能否覆盖官方结论 | 不适用 | 不能 |

社区内容可能受具体型号、批次、安装方式、用户主观感受和原帖准确性影响，因此不能作为官方规格或确定性兼容结论。涉及具体尺寸、支持列表和安装限制时，应以官方说明书、厂商产品页或实际产品参数为准；ToolAgent 的结构化规则判断同样优先于社区经验。

## usage_policy

> 社区经验仅作为装机风险提示，不代表官方规格结论。

当 RAG 使用社区来源时：

1. 官方说明书与社区经验同时命中，官方结论优先，社区经验只作补充。
2. 只有社区经验命中，回答使用“可能”“建议核对”等保守语气，不输出确定性规格。
3. 回答末尾必须展示 usage policy，并提醒用户最终以官方说明书或实际产品参数为准。
4. Trace 的 `sources` 保留 `source_type=community_experience`，便于审计。

## Manifest 校验与规模

Hermes 校验结果：

```text
Verification: PASS
OK | entries=26 topics=10 urls=26 review=4 low=2 medium=24
```

当前规模：

- entries：26
- topics：10
- urls：26
- needs_review：4
- confidence low：2
- confidence medium：24

## 导入与处理

```powershell
python backend/scripts/import_community_experience_seed.py
python backend/scripts/process_knowledge.py
```

导入脚本按 Markdown 的 SHA-256 `file_hash` 幂等去重。首次运行在 `knowledge_documents` 创建一个待处理文档；重复运行返回 `skipped`，不会创建重复文档。随后沿用现有知识处理流水线完成切片和向量化，不清空 Chroma，也不删除已有知识。

## 后续扩展

- 扩充更多机箱、散热器、显卡厚度和走线主题，同时保持来源 URL 可追溯。
- 将 needs_review 条目纳入人工复核工作流。
- 增加主题级召回、来源置信度和时间衰减策略。
- 增加官方规格与社区经验冲突检测和可视化审计。
- 用更多真实问法扩充 Evaluation 回归集。
