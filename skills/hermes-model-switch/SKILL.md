---
name: hermes-model-switch
description: "Hermes Agent 模型/Provider 切换技能 — 配置自定义 Provider、切换模型、管理多 Key 负载均衡"
version: 20260605.1200
author: bonaluo
tags: [hermes, model-switch, provider, nvidia, openrouter, deepseek]
---

# Hermes Agent 模型/Provider 切换

在 Hermes Agent 中切换模型和 Provider 的完整指南。

## 核心命令

### 交互式切换

```bash
hermes model             # 交互式模型/Provider 选择器
hermes config edit       # 编辑完整配置
```

### 命令行切换

```bash
hermes config set model.default "anthropic/claude-sonnet-4"
hermes config set model.provider "openrouter"
```

### 单次对话指定

```bash
hermes chat -m anthropic/claude-sonnet-4 --provider openrouter
hermes chat -m deepseek/deepseek-v4-pro --provider deepseek
```

## 自定义 Provider 配置

### 通过 `custom_providers`

在 `~/.hermes/config.yaml` 中：

```yaml
custom_providers:
  nvidia:
    base_url: https://integrate.api.nvidia.com/v1
    api_key_env: NVIDIA_API_KEY
    models:
      - deepseek-ai/deepseek-v4-pro
      - deepseek-v4-flash
```

**重要：** 使用自定义 Provider 时，`--provider` 和 `-m` 必须同时指定：

```bash
hermes --provider custom:nvidia -m deepseek-ai/deepseek-v4-pro
```

单用 `-m` 不行（仍然走默认 provider）。

### Provider 前缀格式

| 配置方式 | 命令行前缀 |
|----------|-----------|
| 官方 provider | `openrouter`, `anthropic`, `deepseek` |
| 自定义 provider | `custom:<name>` |

### 负载均衡（多 Key）

```yaml
credential_pools:
  nvidia:
    strategy: least_used
    credentials:
      - key: ${NVIDIA_API_KEY}
        request_count: 0
        last_status: ok
      - key: ${NVIDIA_API_KEY_2}
        request_count: 0
        last_status: ok
```

管理命令：

```bash
hermes auth list                   # 查看凭据池
hermes auth add                    # 添加凭据
hermes auth remove nvidia 0        # 删除指定索引
hermes auth reset nvidia           # 重置耗尽状态
```

## 配置检查

修改配置后必须验证：

```bash
hermes doctor                      # 检查配置和依赖
```

## 常用 Provider 环境变量

| Provider | 环境变量 | 说明 |
|----------|---------|------|
| OpenRouter | `OPENROUTER_API_KEY` | 多模型聚合 |
| Anthropic | `ANTHROPIC_API_KEY` | Claude 系列 |
| DeepSeek | `DEEPSEEK_API_KEY` | DeepSeek 系列 |
| NVIDIA | `NVIDIA_API_KEY` | NVIDIA NIM |
| xAI/Grok | `XAI_API_KEY` | Grok 系列 |
| Google Gemini | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Gemini 系列 |
| GitHub Copilot | `COPILOT_GITHUB_TOKEN` | Copilot 模型 |

## 子代理模型

在 `config.yaml` 中单独配置子代理使用的模型：

```yaml
delegation:
  model: "deepseek-v4-flash"
  provider: "custom:nvidia"
```

## 注意事项

1. 切换模型后需要 `/reset` 或新会话才能生效
2. 自定义 Provider 使用 `custom:<name>` 前缀，而不是裸 provider 名
3. 多 Key 负载均衡策略支持 `least_used` 和 `round_robin`
4. NVIDIA NIM 每 Key 限流约 40 RPM
