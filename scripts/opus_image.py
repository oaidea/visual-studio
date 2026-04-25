#!/usr/bin/env python3
"""Direct image generation helper for Visual Studio skill."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_PROVIDER = "openai-image"
DEFAULT_BASE_URL = "https://opus.qzz.io/v1"
OJBK_BASE_URL = "https://ojbkapi.com/v1"
CODEX_BASE_URL = "https://codex.ooooo.codes/v1"
BASE_URL_ALIASES = {
    "opus": DEFAULT_BASE_URL,
    "ojbk": OJBK_BASE_URL,
    "codex": CODEX_BASE_URL,
    "lsj": OJBK_BASE_URL,
}
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_GEMINI_NATIVE_MODEL = "gemini-2.5-flash-image"
PROVIDERS = ("openai-image", "gemini-native")
PROVIDER_ALIASES = {"vs:gpt": "openai-image", "vs:gemini": "gemini-native"}
PROVIDER_CHOICES = PROVIDERS + tuple(PROVIDER_ALIASES)
DEFAULT_SIZE = "1024x1024"
DEFAULT_OUTPUT = "/tmp/opus-image.png"
CONFIG_PATH = Path.home() / ".openclaw/visual-studio/config.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _write_private_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def _config() -> dict[str, Any]:
    return _load_json(CONFIG_PATH) or {}


def normalize_provider(provider: str | None) -> str | None:
    if provider is None:
        return None
    return PROVIDER_ALIASES.get(provider, provider)


def configured_default_provider() -> str:
    cfg = _config()
    provider = normalize_provider(cfg.get("defaultProvider") if isinstance(cfg.get("defaultProvider"), str) else None)
    if isinstance(provider, str) and provider in PROVIDERS:
        return provider
    return DEFAULT_PROVIDER


def configured_default_model(provider: str) -> str:
    cfg = _config()
    defaults = cfg.get("defaults")
    if isinstance(defaults, dict):
        item = defaults.get(provider)
        if isinstance(item, dict):
            model = item.get("model")
            if isinstance(model, str) and model.strip():
                return model.strip()
    return default_model(provider)


def set_default(provider: str, model: str | None = None) -> dict[str, Any]:
    provider = normalize_provider(provider) or DEFAULT_PROVIDER
    cfg = _config()
    cfg["defaultProvider"] = provider
    if model and model.strip():
        defaults = cfg.get("defaults")
        if not isinstance(defaults, dict):
            defaults = {}
        item = defaults.get(provider)
        if not isinstance(item, dict):
            item = {}
        item["model"] = model.strip()
        defaults[provider] = item
        cfg["defaults"] = defaults
    _write_private_json(CONFIG_PATH, cfg)
    return cfg


def _provider_config(provider: str) -> dict[str, Any]:
    cfg = _config()
    providers = cfg.get("providers")
    if isinstance(providers, dict):
        item = providers.get(provider)
        if isinstance(item, dict):
            return item
    # Backward compatibility for the original single Opus key format.
    if provider == "openai-image":
        return cfg
    if provider == "gemini-native":
        native_cfg = dict(cfg)
        base_url = native_cfg.get("baseUrl")
        if isinstance(base_url, str) and base_url.rstrip("/").endswith("/v1"):
            native_cfg["baseUrl"] = base_url.rstrip("/")[:-3]
        return native_cfg
    return {}


def default_base_url(provider: str) -> str:
    if provider == "gemini-native":
        return DEFAULT_BASE_URL.removesuffix("/v1")
    return DEFAULT_BASE_URL


def default_model(provider: str) -> str:
    if provider == "gemini-native":
        return DEFAULT_GEMINI_NATIVE_MODEL
    return DEFAULT_MODEL


def set_api_key(api_key: str, base_url: str | None, provider: str) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("empty API key")

    cfg = _config()
    if provider == "openai-image":
        # Preserve the historic top-level shape for old callers.
        cfg["apiKey"] = key
        cfg["baseUrl"] = normalize_base_url(base_url) or DEFAULT_BASE_URL
    else:
        providers = cfg.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        item = providers.get(provider)
        if not isinstance(item, dict):
            item = {}
        item["apiKey"] = key
        item["baseUrl"] = normalize_base_url(base_url) or default_base_url(provider)
        providers[provider] = item
        cfg["providers"] = providers
    _write_private_json(CONFIG_PATH, cfg)


def clear_api_key(provider: str | None) -> bool:
    if not CONFIG_PATH.exists():
        return False
    if provider is None:
        CONFIG_PATH.unlink()
        return True

    cfg = _config()
    removed = False
    if provider == "openai-image":
        for key in ("apiKey", "baseUrl"):
            if key in cfg:
                cfg.pop(key, None)
                removed = True
    providers = cfg.get("providers")
    if isinstance(providers, dict) and provider in providers:
        providers.pop(provider, None)
        removed = True
    _write_private_json(CONFIG_PATH, cfg)
    return removed


def reset_config() -> bool:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        return True
    return False


def init_config(openai_key: str | None = None, gemini_key: str | None = None, default_provider: str | None = None, default_model_value: str | None = None) -> dict[str, Any]:
    if openai_key and openai_key.strip():
        set_api_key(openai_key, None, "openai-image")
    if gemini_key and gemini_key.strip():
        set_api_key(gemini_key, None, "gemini-native")
    if default_provider:
        set_default(default_provider, default_model_value)

    provider = configured_default_provider()
    model = configured_default_model(provider)
    configured = configured_providers()
    missing = [name for name, ok in configured.items() if not ok]
    ready = bool(configured.get(provider))
    return {
        "ok": ready,
        "ready": ready,
        "config": str(CONFIG_PATH),
        "defaultProvider": provider,
        "defaultModel": model,
        "providers": configured,
        "missingProviders": missing,
        "nextSteps": [] if ready else [
            f"python3 scripts/opus_image.py setkey --provider {provider} '<api-key>'",
            "python3 scripts/opus_image.py init",
        ],
    }


def resolve_api_key(explicit: str | None, provider: str) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    cfg = _provider_config(provider)
    key = cfg.get("apiKey")
    if isinstance(key, str) and key.strip():
        return key.strip()
    env_names = {
        "openai-image": ("OPUS_API_KEY", "OPENAI_API_KEY"),
        "gemini-native": ("VIVGRID_API_KEY", "OPUS_API_KEY", "OPENAI_API_KEY"),
    }.get(provider, ())
    for name in env_names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def normalize_base_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None
    raw = value.strip()
    return BASE_URL_ALIASES.get(raw, raw).rstrip("/")


def resolve_base_url(explicit: str | None, provider: str) -> str:
    normalized = normalize_base_url(explicit)
    if normalized:
        return normalized
    cfg = _provider_config(provider)
    base_url = cfg.get("baseUrl")
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return default_base_url(provider)


def post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int, provider: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    headers["Authorization"] = "Bearer " + api_key

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:2000]}") from exc


def _strip_data_url(value: str) -> tuple[str, str | None]:
    match = re.match(r"^data:([^;]+);base64,(.*)$", value, re.DOTALL)
    if match:
        return match.group(2), match.group(1)
    return value, None


def _find_b64_image(obj: Any) -> tuple[str | None, str | None]:
    if isinstance(obj, dict):
        inline_data = obj.get("inlineData") or obj.get("inline_data")
        if isinstance(inline_data, dict):
            data = inline_data.get("data")
            if isinstance(data, str) and data.strip():
                return _strip_data_url(data)

        for key in ("b64_json", "data", "image", "image_base64"):
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                if key == "data" and len(value) < 128:
                    continue
                return _strip_data_url(value)

        image_url = obj.get("image_url")
        if isinstance(image_url, dict):
            url = image_url.get("url")
            if isinstance(url, str) and url.startswith("data:"):
                return _strip_data_url(url)
        if isinstance(image_url, str) and image_url.startswith("data:"):
            return _strip_data_url(image_url)

        for value in obj.values():
            found, mime = _find_b64_image(value)
            if found:
                return found, mime
    elif isinstance(obj, list):
        for item in obj:
            found, mime = _find_b64_image(item)
            if found:
                return found, mime
    elif isinstance(obj, str) and obj.startswith("data:image/"):
        return _strip_data_url(obj)
    return None, None


def _find_image_url(obj: Any) -> str | None:
    if isinstance(obj, dict):
        for key in ("url", "image_url"):
            value = obj.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
            if isinstance(value, dict):
                nested = value.get("url")
                if isinstance(nested, str) and nested.startswith(("http://", "https://")):
                    return nested
        for value in obj.values():
            found = _find_image_url(value)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_image_url(item)
            if found:
                return found
    elif isinstance(obj, str):
        markdown = re.search(r"!\[[^\]]*\]\((https?://[^\s)]+)", obj)
        if markdown:
            return markdown.group(1)
        plain = re.search(r"https?://[^\s)]+", obj)
        if plain:
            url = plain.group(0).rstrip(".,;。)，）]\"\'")
            if re.search(r"\.(png|jpe?g|webp|gif)(\?|$)", urllib.parse.urlsplit(url).path, re.I) or "image" in url:
                return url
    return None


def download_image(url: str, output_arg: str, timeout: int, output_format: str) -> Path:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if not data:
        raise RuntimeError("image URL returned empty body")
    output = Path(output_arg)
    ext = _extension_for_mime(content_type or None, output_format)
    if output.exists() and output.is_dir():
        output = output / f"visual-studio-{int(time.time())}{ext}"
    elif content_type and output.suffix.lower() != ext:
        output = output.with_suffix(ext)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    return output


def _extension_for_mime(mime: str | None, output_format: str) -> str:
    if mime == "image/jpeg":
        return ".jpg"
    if mime == "image/webp":
        return ".webp"
    if mime == "image/png":
        return ".png"
    return "." + output_format.lstrip(".")


def write_image(output_arg: str, b64: str, mime: str | None, output_format: str) -> Path:
    output = Path(output_arg)
    if output.exists() and output.is_dir():
        output = output / f"visual-studio-{int(time.time())}{_extension_for_mime(mime, output_format)}"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(b64))
    return output


def generate_openai_image(args: argparse.Namespace, api_key: str) -> tuple[dict[str, Any], str, str | None]:
    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "n": args.count,
        "output_format": args.output_format,
        "moderation": args.moderation,
        "background": args.background,
    }
    base_url = resolve_base_url(args.base_url, args.provider)
    if not base_url:
        raise RuntimeError(f"missing base URL for provider {args.provider}; pass --base-url or save one with setkey")
    url = base_url + "/images/generations"
    obj = post_json(url, api_key, payload, args.timeout, args.provider)
    b64, mime = _find_b64_image(obj.get("data") or obj)
    if not b64:
        raise RuntimeError("response has no image base64 data")
    return obj, b64, mime



def _aspect_ratio_from_size(size: str | None) -> str | None:
    if not size or "x" not in size:
        return None
    try:
        w, h = [int(part) for part in size.lower().split("x", 1)]
    except ValueError:
        return None
    if w <= 0 or h <= 0:
        return None
    import math
    g = math.gcd(w, h)
    return f"{w // g}:{h // g}"


def generate_gemini_native(args: argparse.Namespace, api_key: str) -> tuple[dict[str, Any], str, str | None]:
    # NewAPI Gemini native image relay: /v1beta/models/{model}:generateContent/
    generation_config: dict[str, Any] = {"responseModalities": ["TEXT", "IMAGE"]}
    # Do not infer Gemini native imageConfig from OpenAI-style --size by default.
    # Some relayed Gemini models reject aspectRatio/imageSize even while image
    # generation itself works without imageConfig.
    payload: dict[str, Any] = {
        "contents": [{"role": "user", "parts": [{"text": args.prompt}]}],
        "generationConfig": generation_config,
    }
    base_url = resolve_base_url(args.base_url, args.provider)
    if not base_url:
        raise RuntimeError(f"missing base URL for provider {args.provider}; pass --base-url or save one with setkey")
    url = base_url.rstrip("/") + f"/v1beta/models/{args.model}:generateContent/"
    obj = post_json(url, api_key, payload, args.timeout, args.provider)
    b64, mime = _find_b64_image(obj)
    if b64:
        return obj, b64, mime
    image_url = _find_image_url(obj)
    if image_url:
        output = download_image(image_url, args.output, args.timeout, args.output_format)
        return {**obj, "_downloaded_image_url": image_url, "_downloaded_path": str(output)}, "", "url"
    raise RuntimeError("Gemini native response has no image base64 data or image URL")

def configured_providers() -> dict[str, bool]:
    return {provider: bool(resolve_api_key(None, provider)) for provider in PROVIDERS}


def main() -> int:
    parser = argparse.ArgumentParser(description="Visual Studio direct image generation helper")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate an image")
    gen.add_argument("--prompt", required=True, help="Image prompt")
    gen.add_argument("--output", default=DEFAULT_OUTPUT, help="Output image path or directory")
    gen.add_argument("--size", default=DEFAULT_SIZE, help="Image size for OpenAI image endpoint, e.g. 1024x1024")
    gen.add_argument("--provider", default=None, choices=PROVIDER_CHOICES, help="Provider override for this run; omit to use configured default. Aliases: vs:gpt, vs:gemini")
    gen.add_argument("--model", default=None, help="Model override for this run; omit to use provider default/configured default")
    gen.add_argument("--base-url", default=None, help="Provider base URL or alias: opus, ojbk, codex")
    gen.add_argument("--api-key", default=None, help="One-shot API key; not saved")
    gen.add_argument("--timeout", type=int, default=600, help="Request timeout seconds")
    gen.add_argument("--background", default="opaque", choices=["opaque", "transparent", "auto"])
    gen.add_argument("--moderation", default="low", choices=["low", "auto"])
    gen.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    gen.add_argument("--count", type=int, default=1)

    init = sub.add_parser("init", help="Initialize/check Visual Studio API key configuration")
    init.add_argument("--openai-key", default=None, help="Optional key for openai-image; prefer setkey to avoid shell history")
    init.add_argument("--gemini-key", default=None, help="Optional key for gemini-native; prefer setkey to avoid shell history")
    init.add_argument("--default-provider", default=None, choices=PROVIDERS)
    init.add_argument("--default-model", default=None)

    reset = sub.add_parser("reset", help="Reset Visual Studio private config; requires --yes")
    reset.add_argument("--yes", action="store_true", help="Confirm deletion of ~/.openclaw/visual-studio/config.json")

    setkey = sub.add_parser("setkey", help="Save API key to Visual Studio private config")
    setkey.add_argument("key", help="Provider API key")
    setkey.add_argument("--provider", default=DEFAULT_PROVIDER, choices=PROVIDER_CHOICES)
    setkey.add_argument("--base-url", default=None, help="Base URL to save, or alias: opus, ojbk, codex")

    clearkey = sub.add_parser("clearkey", help="Delete saved Visual Studio API key")
    clearkey.add_argument("--provider", default=None, choices=PROVIDER_CHOICES)

    setdefault = sub.add_parser("set-default", help="Set default provider/model for future generate calls")
    setdefault.add_argument("--provider", required=True, choices=PROVIDERS)
    setdefault.add_argument("--model", default=None, help="Optional default model for the provider")

    sub.add_parser("status", help="Show whether provider keys/defaults are configured without revealing keys")

    sub.add_parser("baseurls", help="List built-in base URL aliases")

    # Backward compatibility: allow old --prompt ... invocation as generate.
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.argv.insert(1, "generate")

    args = parser.parse_args()

    if args.command == "init":
        result = init_config(args.openai_key, args.gemini_key, args.default_provider, args.default_model)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ready"] else 2
    if args.command == "reset":
        if not args.yes:
            print("ERROR: reset deletes Visual Studio private config; rerun with --yes to confirm", file=sys.stderr)
            return 2
        removed = reset_config()
        print(json.dumps({"ok": True, "removed": removed, "config": str(CONFIG_PATH), "requiresInit": True, "nextSteps": ["python3 scripts/opus_image.py setkey --provider openai-image '<api-key>'", "python3 scripts/opus_image.py init"]}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "setkey":
        args.provider = normalize_provider(args.provider) or DEFAULT_PROVIDER
        set_api_key(args.key, args.base_url, args.provider)
        print(json.dumps({"ok": True, "provider": args.provider, "config": str(CONFIG_PATH), "baseUrl": resolve_base_url(None, args.provider)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clearkey":
        args.provider = normalize_provider(args.provider)
        removed = clear_api_key(args.provider)
        print(json.dumps({"ok": True, "removed": removed, "provider": args.provider, "config": str(CONFIG_PATH)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "set-default":
        set_default(args.provider, args.model)
        print(json.dumps({"ok": True, "defaultProvider": configured_default_provider(), "defaultModel": configured_default_model(configured_default_provider()), "config": str(CONFIG_PATH)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "baseurls":
        print(json.dumps({"aliases": BASE_URL_ALIASES}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        cfg = _config()
        default_provider = configured_default_provider()
        print(json.dumps({"config": str(CONFIG_PATH), "providers": configured_providers(), "baseUrls": {p: resolve_base_url(None, p) for p in PROVIDERS}, "defaultProvider": default_provider, "defaultModel": configured_default_model(default_provider), "defaults": cfg.get("defaults") if isinstance(cfg.get("defaults"), dict) else {}, "legacyConfig": "apiKey" in cfg}, ensure_ascii=False, indent=2))
        return 0
    if args.command != "generate":
        parser.print_help()
        return 1

    args.provider = normalize_provider(args.provider) or configured_default_provider()
    args.model = args.model or configured_default_model(args.provider)
    api_key = resolve_api_key(args.api_key, args.provider)
    if not api_key:
        print(f"ERROR: missing API key. Run: {sys.argv[0]} setkey --provider {args.provider} '<key>'", file=sys.stderr)
        return 2

    try:
        if args.provider == "gemini-native":
            obj, b64, mime = generate_gemini_native(args, api_key)
        else:
            obj, b64, mime = generate_openai_image(args, api_key)
        if mime == "url":
            output = Path(obj["_downloaded_path"])
        else:
            output = write_image(args.output, b64, mime, args.output_format)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    result = {
        "ok": True,
        "path": str(output),
        "provider": args.provider,
        "model": args.model,
        "size": args.size if args.provider in ("openai-image", "gemini-native") else None,
        "mime": mime,
        "revised_prompt": _extract_revised_prompt(obj),
        "usage": obj.get("usage") or obj.get("usageMetadata"),
        "image_url": obj.get("_downloaded_image_url"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _extract_revised_prompt(obj: dict[str, Any]) -> Any:
    data = obj.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0].get("revised_prompt")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
