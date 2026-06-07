---
name: hermes-model-switch
description: Interactive 3-step model switching for Hermes Agent + helper script to list keyed providers and fetch available models. Supports quick-switch via config/cache.json / Hermes Agent 三步交互式模型切换引导 + 辅助脚本(列出已配 key 的 provider / 拉取可用 model list)。支持通过 config/cache.json 快捷切换
tags: [hermes, model-switch, provider, switch-model]
metadata:
  version: 20260607.0741
  update-url: https://github.com/bonaluo/hermes-skills@hermes-model-switch
---

# Hermes Agent 模型/Provider 切换

三步交互式引导流程，配合辅助脚本在会话内临时切换模型。支持快捷切换：用户说"切换 xxx 模型"时自动从缓存中匹配。

## 触发判断（先于一切）

收到"切换"相关请求时，**先判断走哪个流程**：

### 走快捷切换 — 用户明确说了模型关键词

关键词夹在"切换"和"模型"之间，或"切换到 xxx"等变体：

- ✅ "切换 deepseek-v4-flash 模型"
- ✅ "切换到 flash"
- ✅ "换 pro 模型"
- ✅ "切 deepseek"

### 走三步流程 — 无具体模型关键词

用户只说"切换模型"而未指定哪个模型：

- ❌ "切换模型" → 三步流程
- ❌ "切换其它模型" → 三步流程
- ❌ "换个模型" → 三步流程
- ❌ "切换其他模型" → 三步流程

**没有关键词 = 不走快捷切换 = 必须走三步交互流程。**

---

## 快捷切换（仅有关键词时）

### 快捷切换流程

1. 从缓存中查找：`python3 scripts/hermes-switch-helper.py cache read <keyword>`
   - keyword 取用户提到的模型关键词（如 "flash", "deepseek", "pro", "mini"）
2. 如果缓存命中（匹配到 provider + model），直接拼接 `/model` 命令发给用户
3. 如果缓存未命中，回退到三步交互流程

### 快捷切换完成后

成功切换后，调用 `cache write` 更新缓存：

```bash
python3 scripts/hermes-switch-helper.py cache write <provider> <model>
```

### 缓存文件格式

`config/cache.json`（与 SKILL.md 同级）：

```json
{
    "models": [
        {
            "provider": "nvidia",
            "model": "deepseek-ai/deepseek-v4-flash",
            "count": 3,
            "lastUsed": 1780779946
        }
    ]
}
```

按 `lastUsed` 降序排列，最近使用的排在最前。`count` 记录切换次数。

---

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

按用户选的 `<provider>` + `<model>` 拼接命令，并**同时**执行 `cache write` 写入缓存：

```bash
python3 scripts/hermes-switch-helper.py cache write <provider> <model>
```

然后单独一条消息发送 `/model` 命令：

```
/model <model> --provider <provider>
```

**单独一条消息发送，纯文本无任何格式**（无反引号、无代码块、无 markdown），方便复制。

> 重要：`cache write` 必须在发 `/model` 命令前执行，确保无论用户是否实际执行切换，provider+model 组合都被记录到缓存中。

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

放在 `scripts/` 下，三个子命令：

### `providers`

从 `~/.hermes/config.yaml` 的 `model.provider` / `custom_providers` / `fallback_providers` + `~/.hermes/.env` 的 Key 配对，输出"已配 Key 的 Provider"列表。只输出已配 Key 的。

### `models <provider>`

读取对应 Provider 的 Key，调用 `<base_url>/models` GET 端点获取实时 Model 列表。live fetch 失败时回退 `~/.hermes/provider_models_cache.json` 缓存。

内置 Provider 映射包括：nvidia、lm-studio、openai、anthropic、minimax、minimax-cn、openrouter、kimi-coding、zai、custom 等。

### `cache read [<keyword>]`

从同级的 `config/cache.json` 读取快捷切换缓存。keyword 可选，匹配 model 或 provider 名称。按 `lastUsed` 降序输出 JSON 行。

### `cache write <provider> <model>`

写入一条快捷切换记录。同 provider+model 已存在则 count+1 并更新 lastUsed。