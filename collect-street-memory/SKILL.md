---
name: collect-street-memory
description: 访谈并忠实整理用户对单个、时空连续的童年街道场景记忆。用于收集原始描述、识别场景连续性，并提取氛围、植物、建筑、街道设施、人物和交通工具；不得美化、推断或用常识补全。
---

# 采集街道记忆

邀请用户自由描述一个时空连续的童年街道场景。完整保留第一轮原话，不中途逐项打断。

## 规则

- 只处理同一时间段、相连空间中可自然串联的一个场景。
- 若出现多个时间或地点，列出场景并请用户选择一个；选择前不混合整理。
- 每轮只针对影响还原的缺失或含糊信息提出少量开放式问题。
- 不美化、不现代化、不历史化补全，不猜测人物身份。
- 未提供写“未提及”，明确记不清写“用户记不清”。

重点提取氛围、植物、建筑、街道设施、人物、交通工具，以及用户明确表达的种类、位置、数量、状态、活动和空间关系。

## 输出契约

输出 Markdown 摘要供用户确认，同时维护以下 JSON 语义：

```json
{
  "raw_memory_text": "按访谈顺序忠实记录",
  "structured_memory": {
    "scene_continuity": {"selected_scene": "", "time_space": "", "excluded_scenes": []},
    "atmosphere": [], "plants": [], "buildings": [], "street_facilities": [],
    "people": [], "vehicles": [], "spatial_relations": [],
    "uncertain_fields": [], "inferred_elements": []
  },
  "unresolved_questions": [],
  "user_confirmed": false
}
```

最后询问记录是否忠实、哪里需要更正或补充。只有用户明确确认后把 `user_confirmed` 设为 `true`。
