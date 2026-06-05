---
name: hermes-model-switch
description: Interactive 3-step model switching for Hermes Agent + helper script to list keyed providers and fetch available models / Hermes Agent 三步交互式模型切换引导 + 辅助脚本(列出已配 key 的 provider / 拉取可用 model list)
tags: [hermes, model-switch, provider, switch-model]
metadata:
  version: 20260605.2236
  update-url: https://github.com/bonaluo/hermes-skills@hermes-model-switch
---

# Hermes Agent 模型/Provider 切换

三步交互式引导流程，配合辅助脚本在会话内临时切换模型。

## 交互式引导（三步流程）

流程严格三步，每步等待用户回复。

运行辅助脚本前，先通过 `skill_view('hermes-model-switch')` 获取 skill 目录，然后以相对路径 `scripts/hermes-switch-helper.py` 调用。

### 步骤 1：列出已配 Key 的 Provider

```bash
python3 scripts/hermes-switch-helper.py providers
```

输出格式：`<n>. <provider_name>`，只发编号 + 名称。

> 注意：脚本依赖 PyYAML（在 Hermes venv 中已自带）。如果系统 python3 没有 yaml 模块，脚本会自动尝试缓存或降级处理。

### 步骤 2：用户选 Provider 后，拉取可用 Model 列表

```bash
python3 scripts/hermes-switch-helper.py models <provider_name>
```

输出格式：`<n>. <model_id>`，当前主 model 标注 ←。

### 步骤 3：用户选 Model 后，生成 `/model` 命令

按用户选的 `<provider>` + `<model>` 拼接：

```
/model <model> --provider <provider>
```

**单独一条消息发送，纯文本无任何格式**（无反引号、无代码块、无 markdown），方便复制。

### 沟通规范

- **回复简洁**：只发编号 + 名称，不要表格 / 备注 / 未配 key 列表
- **第 3 步命令**：单独一条消息，纯文本无格式（不包裹反引号/代码块）
- **不要自作主张**：每步等用户回复，不跳步

### 关键约束

- "切换模型" = **会话中临时切换**，不写 `config.yaml`（不带 `--global`）
- 用 Hermes 自带的 `/model` slash 命令，不是改 `config.yaml`
- Agent **不替用户发 `/model`** — slash command 是 user-side 触发的，只能用户发

---

## 辅助脚本 `hermes-switch-helper.py`

放在 `scripts/` 下，两个子命令：

### `providers`

从 `~/.hermes/config.yaml` 的 `model.provider` / `custom_providers` / `fallback_providers` + `~/.hermes/.env` 的 Key 配对，输出"已配 Key 的 Provider"列表。只输出已配 Key 的。

### `models <provider>`

读取对应 Provider 的 Key，调用 `<base_url>/models` GET 端点获取实时 Model 列表。live fetch 失败时回退 `~/.hermes/provider_models_cache.json` 缓存。

内置 Provider 映射包括：nvidia、lm-studio、openai、anthropic、minimax、minimax-cn、openrouter、kimi-coding、zai、custom 等。
