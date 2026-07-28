---
name: jimeng-text-to-image
description: 通过火山引擎即梦文生图 3.0 API 从用户已确认的 prompt 生成图像，返回图像 URL 或沙箱文件路径并保存原始响应。用于阿里云百炼 Agent、记忆街道工作流或用户明确要求调用或测试即梦 API 时；使用环境变量凭证和 bundled runner，不得把 AK/SK 写入对话、文件、命令参数、日志或最终输出。
---

# 即梦文生图

使用随 Skill 打包的 `scripts/jimeng_t2i.py` 调用即梦文生图 3.0。不要重新实现签名、提交或轮询逻辑。

## 定位与执行脚本

激活 Skill 后，只使用平台实际返回的 Skill 根目录（例如 `skill_directory` 或 `sandbox_path`）定位脚本：

```text
<skill_root>/scripts/jimeng_t2i.py
```

先确认该文件存在，再从 `<skill_root>` 目录执行。不要假定 Skill 位于 `/root/workspace`、`/home/workspace` 或当前工作目录，也不要在路径失败后自行替换 `/root`、`/home` 并循环重试。

若平台没有返回可访问的 Skill 根目录、没有提供 Python/代码执行工具，或脚本不存在，立即返回一次结构化错误并停止：

```json
{"status":"error","code":"SKILL_RUNTIME_UNAVAILABLE","message":"jimeng-text-to-image 的执行目录或 Python 运行时不可用"}
```

Skill 名称用于触发和加载说明，不等同于可调用的 Function Tool。不得把 `jimeng-text-to-image` 当作工具名调用，除非平台确实注册了同名工具。

## 调用前检查

确认 Agent 环境已配置：

- `VOLCENGINE_ACCESS_KEY_ID`
- `VOLCENGINE_SECRET_ACCESS_KEY`

若缺失，停止并报告缺失的环境变量名称，不要要求用户在对话中提供密钥。真实调用前确认用户已经确认 prompt；测试参数或部署连通性时先使用 `--dry-run`，该模式不需要凭证且不联网。

## 输入

必填：

- `prompt`：正向提示词，最多 800 字符；超过 120 字符时提示可能超出 API 推荐长度。

可选：

- `negative_prompt`：负向提示词，默认空。
- `width`、`height`：默认 `1328`。
- `count`：本轮最终必须取得的图片数量，默认 `4`，范围 `1` 至 `4`；不得拆分调用以绕过每轮最多 4 张的限制。
- `seed`：默认 `-1`。
- `use_pre_llm`：默认 `true`。
- `add_logo`：默认 `false`。
- `poll_interval`：默认 `3` 秒。
- `timeout`：默认 `180` 秒。
- `output_dir`：默认 `outputs`。

直接调用：

```bash
python scripts/jimeng_t2i.py --prompt "已确认的正向提示词" --negative-prompt "负向提示词" --count 4 --output-dir outputs
```

也可把非敏感参数写入 JSON 文件后调用：

```json
{
  "prompt": "雨后的老街，青石板路，暖色灯光，纪实摄影风格",
  "negative_prompt": "现代汽车，霓虹灯，文字，水印",
  "width": 1328,
  "height": 1328,
  "count": 4,
  "seed": -1,
  "use_pre_llm": true,
  "add_logo": false,
  "poll_interval": 3,
  "timeout": 180,
  "output_dir": "outputs"
}
```

```bash
python scripts/jimeng_t2i.py --payload-file payload.json
```

命令行参数覆盖 JSON 文件中的同名参数。payload 文件不得包含 AK/SK。

## 执行与返回

runner 使用以下固定 API 配置：

- endpoint：`https://visual.volcengineapi.com`
- submit action：`CVSync2AsyncSubmitTask`
- result action：`CVSync2AsyncGetResult`
- version：`2022-08-31`
- service：`cv`
- region：`cn-north-1`
- req_key：`jimeng_t2i_v30`

执行提交、读取 `task_id`、轮询结果并输出单行 JSON。`count` 是最终数量契约：若一个已完成任务返回的图片少于请求数量，runner 会按剩余数量低频串行提交后续任务，直到取得准确数量；不得由 Agent 另行并发补图。任何任务返回零张图或 API 错误时立即停止，不进行高频重试。

成功结果包含 `status`、`task_id`、`task_ids`、`request_id`、`request_ids`、`requested_count`、`generated_count`、`images`、`raw_result_path` 和 `raw_result_paths`。只有 `status=done` 且 `generated_count=requested_count=count` 才视为成功。`task_id` 保留首个任务 ID 以兼容旧调用，完整任务列表使用 `task_ids`。`images[].image_index` 在所有任务间连续且稳定。优先返回 `images[].url`；若只得到 Base64，则保存为沙箱文件并返回 `local_path`。`raw_result_path` 指向汇总清单，`raw_result_paths` 保存逐任务原始响应，供审计和后续交付。

失败时报告 `request_id`、`code` 和 `message`。遇到 `50429` 或 `50430` 时说明触发 QPS 或并发限制，不要高频自动重试。遇到内容安全拒绝时，要求用户修改 prompt 后再试。不得显示完整 AK/SK。

脚本成功输出单行 JSON 后，直接把 `images` 返回给用户并结束本轮，不要重新激活 Skill 或再次进入生成规划。脚本输出 `status=error` 或进程非零退出时，只报告该错误一次；除非用户明确要求，不自动重试。
