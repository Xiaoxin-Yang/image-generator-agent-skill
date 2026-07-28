---
name: memory-street-image-calibrator-cn
description: 依据个人街道记忆，对同一记忆生成的 2 至 8 张候选图执行技术质量门禁、记忆硬约束核验、六维评分、排序与再生成建议。用于记忆街道候选图筛选和匹配度评价；不用于直接生成图片或单纯审美排序。
---

# 记忆街道图像校准

只依据图中可见内容和用户确认的记忆评价。区分观察与解释；证据不足时标记不确定，不用常识补全。

## 输入与门禁

必须取得 `memory_text` 和带稳定 `image_index` 的 2 至 8 张 `candidate_images`。优先使用 `structured_memory`。关键、重要、可选元素权重分别为 3、2、1；禁止元素、用户不确定字段和推断元素不得混淆。

先检查严重损坏、拼接破坏、灾难性几何、主要对象严重变形、主要结构异常复制和场景不可判断。再检查关键元素缺失、禁止元素出现、场景类型反转、重大年代冲突、关键空间关系反转和核心活动反转。明确且置信度不低于 0.80 时才判定硬失败。

## 评分与资格

对未被技术否决的图片给整数分：完整性 15、空间逻辑 20、记忆内容 30、时间氛围 15、地方性 10、呈现 10。六维之和必须等于总分。

只有无硬失败、总分至少 78、完整性至少 10、空间至少 14、记忆至少 23、关键元素齐全、加权覆盖率至少 0.75 且置信度至少 0.70 才为 `eligible`。按总分排序；分差小于 4 或证据不足时返回 `human_review`，没有合格图时返回 `regenerate`。

## 输出

只输出一个合法 JSON 对象，不加 Markdown。顶层必须包含 `status`、`rubric_version`、`selection_mode`、`selected_image_index`、`selected_score`、`summary_reason`、`pairwise_confirmation`、`human_review_candidates`、`regeneration_plan` 和逐图 `details`。每个 detail 必须包含技术门禁、记忆硬失败、可见描述、覆盖率、缺失项、禁止项、新增项、六维分、总分、资格、置信度、优点和弱点。
