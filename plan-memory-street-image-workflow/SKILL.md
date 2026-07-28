---
name: plan-memory-street-image-workflow
description: 编排童年街道记忆图像工作流。用于采集连续街道记忆、确认结构化场景、通过即梦生成候选图，并依据记忆约束循环评估直至获得三张合格图像。必须依次使用 collect-street-memory、jimeng-text-to-image 和 memory-street-image-calibrator-cn。
---

# 记忆街道图像工作流

严格按阶段执行。不得在用户确认前生成图片，不得把推断写成用户记忆。

## 依赖检查

开始前确认可用 skill 包含 `collect-street-memory`、`jimeng-text-to-image` 和 `memory-street-image-calibrator-cn`。若缺失，停止并报告缺失名称，不得假装调用成功。生成阶段还必须确认环境变量 `VOLCENGINE_ACCESS_KEY_ID` 和 `VOLCENGINE_SECRET_ACCESS_KEY` 可用；不得要求用户把密钥写入聊天或文件。

## 阶段 1：采集与确认

使用 `collect-street-memory`，取得 `raw_memory_text`、`structured_memory`、`unresolved_questions` 和 `user_confirmed`。有未解决问题时只继续访谈。展示结构化摘要；只有 `user_confirmed=true` 才进入下一阶段。

## 阶段 2：生成候选图

由已确认记忆按氛围、植物、建筑、街道设施、人物、交通工具的顺序构造正向 prompt。构造 negative prompt，排除人体畸形、漂浮物、不连续道路、错误透视、时代错置、虚构文化符号、旅游景区化和无依据怀旧滤镜。

使用 `jimeng-text-to-image` 每轮生成 2 至 4 张，任何一轮均不得请求或生成超过 4 张；传入正负 prompt、尺寸、seed、输出目录和超时。接收 `status`、`task_ids`、`request_ids`、`requested_count`、`generated_count`、`images`、`raw_result_path` 和 `raw_result_paths`；只有 `status=done` 且 `generated_count=requested_count` 才进入评估。候选不足时由 bundled runner 内部低频串行补齐，不得另行并发提交。保存模型、参数、seed、全部任务 ID 和生成时间。

## 阶段 3：评估与循环

使用 `memory-street-image-calibrator-cn`，输入用户原话、已确认的 `structured_memory` 和带稳定 `image_index` 的候选图。只接受单个合法 JSON。

- 将 `eligible` 且无硬失败的不同图片加入合格池。
- 根据 `regeneration_plan` 修订 prompt，不改变已确认的关键空间关系。
- 合格池达到 3 张时停止。
- 整个工作流最多生成 2 轮。第 2 轮评估完成后，无论合格池是否达到 3 张，都必须停止生成；若仍不足 3 张，交付已有合格图并请用户决定是否另行启动新工作流或调整 prompt、阈值或模型，不得自行开始第 3 轮或降低资格线。

## 阶段 4：交付

展示三张合格图片及短编号，同时保存已确认记忆 JSON、最终正负 prompts、生成元数据、逐图评价和拒绝原因。说明 AIGC 图像不等同于历史事实或原始记忆。
