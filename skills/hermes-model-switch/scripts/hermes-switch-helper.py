#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hermes-switch-helper.py — Hermes 会话内切换模型的辅助脚本

用法:
    hermes-switch-helper.py providers
        列出已配 API key 的 provider(从 config.yaml + .env 推断)。

    hermes-switch-helper.py models <provider>
        调 <base_url>/models 拉取该 provider 的实时 model 列表。
        live fetch 失败时回退 ~/.hermes/provider_models_cache.json。

    hermes-switch-helper.py cache read [<keyword>]
        从 SKILL.md 同级 config/cache.json 读取快捷切换缓存。
        keyword 可选,匹配 model 或 provider 名称。

    hermes-switch-helper.py cache write <provider> <model>
        写入一条快捷切换记录到 config/cache.json。
        同 provider+model 已存在则 count+1 并更新 lastUsed。

依赖: PyYAML (hermes-agent venv 自带)。其余用 stdlib。
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


# ---------------------------------------------------------------------------
# Config / .env 读取
# ---------------------------------------------------------------------------

def _read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _read_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        print(f"  (yaml load failed: {e})", file=sys.stderr)
        return {}


# ---------------------------------------------------------------------------
# Provider 元数据(参考 hermes_cli/auth.py PROVIDER_REGISTRY)
# ---------------------------------------------------------------------------

# 每个 provider 的:base_url 模板 + 用于检测"已配 key"的 env 变量名列表
# 多个 env 候选时,任何一个存在就算配了
PROVIDERS: dict[str, dict] = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "key_envs": ["NVIDIA_API_KEY"],
    },
    "lm-studio": {
        # LM Studio 默认端口 1234;用户可设 LM_STUDIO_BASE_URL 覆盖
        "base_url": os.environ.get("LM_STUDIO_BASE_URL", "http://127.0.0.1:1234/v1"),
        "key_envs": ["LM_API_KEY", "LM_STUDIO_API_KEY"],
    },
    "openai": {
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        "key_envs": ["OPENAI_API_KEY"],
    },
    "anthropic": {
        "base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1"),
        "key_envs": ["ANTHROPIC_API_KEY"],
    },
    "minimax": {
        "base_url": os.environ.get("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic"),
        "key_envs": ["MINIMAX_API_KEY"],
    },
    "minimax-cn": {
        "base_url": os.environ.get("MINIMAX_CN_BASE_URL", "https://api.minimaxi.com/anthropic"),
        "key_envs": ["MINIMAX_CN_API_KEY"],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_envs": ["OPENROUTER_API_KEY"],
    },
    "kimi-coding": {
        "base_url": "https://api.moonshot.cn/v1",
        "key_envs": ["KIMI_API_KEY", "MOONSHOT_API_KEY"],
    },
    "zai": {
        "base_url": "https://api.zhipuai.cn/anthropic",
        "key_envs": ["ZAI_API_KEY", "GLM_API_KEY"],
    },
    "tencent-tokenhub": {
        "base_url": "https://tokenhub.tencent.com/v1",
        "key_envs": ["TENCENT_TOKENHUB_API_KEY"],
    },
    # openai-codex = OAuth,没有 env key;nous = portal 登录
    "openai-codex": {"base_url": None, "key_envs": []},
    "nous":        {"base_url": None, "key_envs": []},
}


# ---------------------------------------------------------------------------
# 子命令 1: providers
# ---------------------------------------------------------------------------

def cmd_providers() -> int:
    cfg = _read_yaml(HERMES_HOME / "config.yaml")
    env = _read_env(HERMES_HOME / ".env")

    model_block = cfg.get("model") or {}
    main_provider = (model_block.get("provider") or "").strip()
    main_default = (model_block.get("default") or "").strip()
    custom = cfg.get("custom_providers") or []
    fallback = cfg.get("fallback_providers") or []

    seen: set[str] = set()
    rows: list[tuple[str, str, bool]] = []  # (provider, role, has_key)

    def _check_key(prov: str) -> bool:
        meta = PROVIDERS.get(prov, {})
        envs = meta.get("key_envs") or []
        if any(env.get(e) for e in envs):
            return True
        # 兜底:<PROV>_API_KEY 形式(把 - 变 _ ,大写)
        generic = f"{prov.upper().replace('-', '_')}_API_KEY"
        return bool(env.get(generic))

    # 1) main
    if main_provider and main_provider not in seen:
        rows.append((main_provider, "main", _check_key(main_provider)))
        seen.add(main_provider)

    # 2) custom_providers(每个独立一行,因为 base_url 可能不同)
    for i, cp in enumerate(custom):
        prov = (cp.get("provider") or "custom").strip()
        if prov in seen:
            continue
        has_key = bool(cp.get("api_key"))
        rows.append((prov, "custom", has_key))
        seen.add(prov)

    # 3) fallback_providers
    for fb in fallback:
        prov = (fb.get("provider") or "").strip()
        if not prov or prov in seen:
            continue
        # fallback 块可能自己带 api_key / key_env
        has_key = bool(fb.get("api_key"))
        if not has_key:
            ke = fb.get("key_env") or fb.get("api_key_env")
            if ke and env.get(ke):
                has_key = True
        if not has_key:
            has_key = _check_key(prov)
        rows.append((prov, "fallback", has_key))
        seen.add(prov)

    n = 0
    printed: set[str] = set()
    for prov, role, has_key in rows:
        if not has_key or prov in printed:
            continue
        n += 1
        # 简短注释(main 时附 default model)
        suffix = ""
        if role == "main" and main_default:
            suffix = f"({main_default})"
        elif role == "custom":
            cp0 = custom[0] if custom else {}
            if cp0.get("name"):
                suffix = f"({cp0['name']})"
        print(f"{n}. {prov}{suffix}")
        printed.add(prov)

    # 兜底:.env 配了 key、但 config.yaml 任何块都没引用的 provider(典型:
    # lm-studio 只在 .env 留了 key 备选、模型块仍用 nvidia)。也算"已配 key 可选"。
    for prov, meta in PROVIDERS.items():
        if prov in printed:
            continue
        envs = meta.get("key_envs") or []
        if not any(env.get(e) for e in envs):
            # 兜底:<PROV>_API_KEY 形式
            generic = f"{prov.upper().replace('-', '_')}_API_KEY"
            if not env.get(generic):
                continue
        n += 1
        print(f"{n}. {prov}")
        printed.add(prov)

    return 0


# ---------------------------------------------------------------------------
# 子命令 2: models <provider>
# ---------------------------------------------------------------------------

def _resolve_custom(cfg: dict) -> tuple[str | None, str | None]:
    """custom 类型的 (base_url, api_key),取 config.yaml.custom_providers[0]."""
    for cp in (cfg.get("custom_providers") or []):
        if (cp.get("base_url") or "").strip():
            return (cp["base_url"].rstrip("/"), cp.get("api_key") or "")
    return (None, None)


def _fetch_live(base_url: str, api_key: str | None) -> list[str]:
    url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(url, method="GET")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            return [m["id"] for m in data["data"] if "id" in m]
        if isinstance(data.get("models"), list):
            return [m.get("id") or m.get("name") or m for m in data["models"]]
    if isinstance(data, list):
        return [m.get("id") if isinstance(m, dict) else m for m in data]
    return []


def _fallback_cache(provider: str) -> list[str]:
    cache_path = HERMES_HOME / "provider_models_cache.json"
    if not cache_path.exists():
        return []
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return list((cache.get(provider) or {}).get("models") or [])


def cmd_models(provider: str) -> int:
    cfg = _read_yaml(HERMES_HOME / "config.yaml")
    env = _read_env(HERMES_HOME / ".env")

    # 解析 base_url + api_key
    base_url: str | None = None
    api_key: str | None = None

    if provider in PROVIDERS and PROVIDERS[provider]["base_url"]:
        meta = PROVIDERS[provider]
        base_url = meta["base_url"]
        for e in meta["key_envs"]:
            if env.get(e):
                api_key = env[e]
                break
    elif provider == "custom":
        base_url, api_key = _resolve_custom(cfg)

    if not base_url:
        print(f"  (no base_url for provider '{provider}'; using cache)", file=sys.stderr)
        for i, m in enumerate(_fallback_cache(provider), 1):
            print(f"{i}. {m}")
        return 0

    # 先 live fetch
    models: list[str] = []
    err: str | None = None
    try:
        models = _fetch_live(base_url, api_key)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        err = str(e)

    if not models:
        if err:
            print(f"  (live fetch failed: {err}; using cache)", file=sys.stderr)
        else:
            print(f"  (live fetch returned empty; using cache)", file=sys.stderr)
        models = _fallback_cache(provider)

    for i, m in enumerate(models, 1):
        print(f"{i}. {m}")
    return 0


# ---------------------------------------------------------------------------
# 子命令 3: cache — 读取/写入快捷切换缓存
# ---------------------------------------------------------------------------

def _cache_path() -> Path:
    """SKILL.md 同级 config/cache.json"""
    script_dir = Path(__file__).resolve().parent  # scripts/
    return script_dir.parent / "config" / "cache.json"


def cmd_cache(action: str, *extra: str) -> int:
    """cache read [<keyword>]  |  cache write <provider> <model>"""
    path = _cache_path()

    if action == "read":
        if not path.exists():
            return 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        keyword = extra[0].lower() if extra else ""
        # 按 lastUsed 降序排列
        models = sorted(
            data.get("models", []),
            key=lambda x: x.get("lastUsed", 0),
            reverse=True,
        )
        for m in models:
            if keyword:
                if keyword not in m.get("model", "").lower() and keyword not in m.get("provider", "").lower():
                    continue
            print(json.dumps(m))
        return 0

    if action == "write":
        if len(extra) < 2:
            print("Usage: hermes-switch-helper.py cache write <provider> <model>", file=sys.stderr)
            return 2
        provider, model = extra[0], extra[1]
        path.parent.mkdir(parents=True, exist_ok=True)
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        models: list[dict] = data.get("models", [])
        now_ts = int(time.time())
        found = False
        for m in models:
            if m.get("provider") == provider and m.get("model") == model:
                m["count"] = m.get("count", 0) + 1
                m["lastUsed"] = now_ts
                found = True
                break
        if not found:
            models.append({
                "provider": provider,
                "model": model,
                "count": 1,
                "lastUsed": now_ts,
            })
        models.sort(key=lambda x: x.get("lastUsed", 0), reverse=True)
        data["models"] = models
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0

    print(f"Unknown cache action: {action}\nUsage: cache read|write ...", file=sys.stderr)
    return 2


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "providers":
        return cmd_providers()
    if cmd == "models":
        if len(argv) < 3:
            print("Usage: hermes-switch-helper.py models <provider>", file=sys.stderr)
            return 2
        return cmd_models(argv[2])
    if cmd == "cache":
        if len(argv) < 3:
            print("Usage: hermes-switch-helper.py cache read|write ...", file=sys.stderr)
            return 2
        return cmd_cache(argv[2], *argv[3:])
    print(f"Unknown command: {cmd}\n{__doc__}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))