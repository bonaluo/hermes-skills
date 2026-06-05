---
name: hermes-model-switch
description: "Hermes Agent 模型/Provider 切换 — 三步交互式引导 + 辅助脚本(列出已配 key 的 provider / 拉取可用 model list) + 配置参考"
version: 20260605.2040
author: bonaluo
tags: [hermes, model-switch, provider, switch-model]
---

# Hermes Agent 模型/Provider 切换

包含两种使用方式：

- **交互式引导**（三步流程）：适合会话内临时切换模型
- **配置参考**：适合持久化配置自定义 Provider、负载均衡等

---

## 交互式引导（三步流程）

流程严格三步，每步等待用户回复。

### 步骤 1：列出已配 Key 的 Provider

运行辅助脚本：

```bash
python3 ~/.hermes/skills/hermes-model-switch/scripts/hermes-switch-helper.py providers
```

输出格式：`<n>. <provider_name>`，只发编号 + 名称。

> 注意：脚本依赖 PyYAML（建议在 Hermes venv 中运行）。如果系统 python3 没有 yaml 模块，脚本会自动尝试缓存或降级处理。

### 步骤 2：用户选 Provider 后，拉取可用 Model 列表

```bash
python3 ~/.hermes/skills/hermes-model-switch/scripts/hermes-switch-helper.py models <provider_name>
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

---

## 配置参考

### 核心命令

```bash
hermes model             # 交互式模型/Provider 选择器
hermes config edit       # 编辑完整配置
```

### 命令行切换（持久化）

```bash
hermes config set model.default "<model>"
hermes config set model.provider "<provider>"
```

### 单次对话指定（临时）

```bash
hermes chat -m <model> --provider <provider>
```

### 自定义 Provider

在 `~/.hermes/config.yaml` 中：

```yaml
custom_providers:
  - provider: nvidia
    base_url: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY
```

使用自定义 Provider 时必须同时指定 `--provider` 和 `-m`：

```bash
hermes --provider custom:nvidia -m deepseek-ai/deepseek-v4-pro
```

### 负载均衡（多 Key）

```yaml
credential_pools:
  nvidia:
    strategy: least_used
    credentials:
      - key: ${NVIDIA_API_KEY}
      - key: ${NVIDIA_API_KEY_2}
```

管理命令：

```bash
hermes auth list                   # 查看凭据池
hermes auth add                    # 添加凭据
hermes auth remove nvidia 0        # 删除指定索引
hermes auth reset nvidia           # 重置耗尽状态
```

### 配置检查

修改配置后验证：

```bash
hermes doctor
```

---

## 环境变量参考

| Provider | 环境变量 | 说明 |
|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | 多模型聚合 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 系列 |
| DeepSeek | `DEEPSEEK_API_KEY` | DeepSeek 系列 |
| NVIDIA | `NVIDIA_API_KEY` | NVIDIA NIM |
| xAI/Grok | `XAI_API_KEY` | Grok 系列 |
| Google Gemini | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini 系列 |
| GitHub Copilot | `COPILOT_GITHUB_TOKEN` | Copilot 模型 |

## 子代理模型

在 `config.yaml` 中单独配置：

```yaml
delegation:
  model: "<model>"
  provider: "<provider>"
```

## 注意事项

1. 切换模型后需要 `/reset` 或新会话才能生效
2. 自定义 Provider 使用 `custom:<name>` 前缀
3. 多 Key 负载均衡策略支持 `least_used` 和 `round_robin`
4. `/model` 命令默认会话内临时生效（不加 `--global`）
