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
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-image"
DEFAULT_OPENAI_CHAT_MODEL = "gemini-2.5-flash-image"
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
    return {}


def default_base_url(provider: str) -> str:
    if provider == "gemini":
        return DEFAULT_GEMINI_BASE_URL
    return DEFAULT_BASE_URL


def default_model(provider: str) -> str:
    if provider == "gemini":
        return DEFAULT_GEMINI_MODEL
    if provider == "openai-chat":
        return DEFAULT_OPENAI_CHAT_MODEL
    return DEFAULT_MODEL


def set_api_key(api_key: str, base_url: str | None, provider: str) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("empty API key")

    cfg = _config()
    if provider == "openai-image":
        # Preserve the historic top-level shape for old callers.
        cfg["apiKey"] = key
        cfg["baseUrl"] = (base_url or DEFAULT_BASE_URL).rstrip("/")
    else:
        providers = cfg.get("providers")
        if not isinstance(providers, dict):
            providers = {}
        item = providers.get(provider)
        if not isinstance(item, dict):
            item = {}
        item["apiKey"] = key
        item["baseUrl"] = (base_url or default_base_url(provider)).rstrip("/")
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


def resolve_api_key(explicit: str | None, provider: str) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    cfg = _provider_config(provider)
    key = cfg.get("apiKey")
    if isinstance(key, str) and key.strip():
        return key.strip()
    env_names = {
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openai-chat": ("OPENAI_API_KEY", "OPUS_API_KEY"),
        "openai-image": ("OPUS_API_KEY", "OPENAI_API_KEY"),
    }.get(provider, ())
    for name in env_names:
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_base_url(explicit: str | None, provider: str) -> str:
    if explicit and explicit.strip():
        return explicit.strip().rstrip("/")
    cfg = _provider_config(provider)
    base_url = cfg.get("baseUrl")
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return default_base_url(provider)


def post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int, provider: str) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if provider == "gemini":
        parsed = urllib.parse.urlsplit(url)
        qs = urllib.parse.parse_qs(parsed.query)
        qs["key"] = [api_key]
        url = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(qs, doseq=True)))
    else:
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
    url = resolve_base_url(args.base_url, args.provider) + "/images/generations"
    obj = post_json(url, api_key, payload, args.timeout, args.provider)
    b64, mime = _find_b64_image(obj.get("data") or obj)
    if not b64:
        raise RuntimeError("response has no image base64 data")
    return obj, b64, mime


def generate_gemini(args: argparse.Namespace, api_key: str) -> tuple[dict[str, Any], str, str | None]:
    payload: dict[str, Any] = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": args.prompt}],
            }
        ],
        "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
    }
    url = resolve_base_url(args.base_url, args.provider) + f"/models/{args.model}:generateContent"
    obj = post_json(url, api_key, payload, args.timeout, args.provider)
    b64, mime = _find_b64_image(obj)
    if not b64:
        raise RuntimeError("Gemini response has no inline image data")
    return obj, b64, mime


def generate_openai_chat(args: argparse.Namespace, api_key: str) -> tuple[dict[str, Any], str, str | None]:
    payload: dict[str, Any] = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "modalities": ["text", "image"],
    }
    url = resolve_base_url(args.base_url, args.provider) + "/chat/completions"
    obj = post_json(url, api_key, payload, args.timeout, args.provider)
    b64, mime = _find_b64_image(obj)
    if not b64:
        raise RuntimeError("chat completions response has no image base64 data")
    return obj, b64, mime


def configured_providers() -> dict[str, bool]:
    return {provider: bool(resolve_api_key(None, provider)) for provider in ("openai-image", "gemini", "openai-chat")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Visual Studio direct image generation helper")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate an image")
    gen.add_argument("--prompt", required=True, help="Image prompt")
    gen.add_argument("--output", default=DEFAULT_OUTPUT, help="Output image path or directory")
    gen.add_argument("--size", default=DEFAULT_SIZE, help="Image size for OpenAI image endpoint, e.g. 1024x1024")
    gen.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["openai-image", "gemini", "openai-chat"])
    gen.add_argument("--model", default=None, help="Model id")
    gen.add_argument("--base-url", default=None, help="Provider base URL")
    gen.add_argument("--api-key", default=None, help="One-shot API key; not saved")
    gen.add_argument("--timeout", type=int, default=600, help="Request timeout seconds")
    gen.add_argument("--background", default="opaque", choices=["opaque", "transparent", "auto"])
    gen.add_argument("--moderation", default="low", choices=["low", "auto"])
    gen.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    gen.add_argument("--count", type=int, default=1)

    setkey = sub.add_parser("setkey", help="Save API key to Visual Studio private config")
    setkey.add_argument("key", help="Provider API key")
    setkey.add_argument("--provider", default=DEFAULT_PROVIDER, choices=["openai-image", "gemini", "openai-chat"])
    setkey.add_argument("--base-url", default=None, help="Base URL to save")

    clearkey = sub.add_parser("clearkey", help="Delete saved Visual Studio API key")
    clearkey.add_argument("--provider", default=None, choices=["openai-image", "gemini", "openai-chat"])
    sub.add_parser("status", help="Show whether provider keys are configured without revealing them")

    # Backward compatibility: allow old --prompt ... invocation as generate.
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.argv.insert(1, "generate")

    args = parser.parse_args()

    if args.command == "setkey":
        set_api_key(args.key, args.base_url, args.provider)
        print(json.dumps({"ok": True, "provider": args.provider, "config": str(CONFIG_PATH), "baseUrl": resolve_base_url(None, args.provider)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clearkey":
        removed = clear_api_key(args.provider)
        print(json.dumps({"ok": True, "removed": removed, "provider": args.provider, "config": str(CONFIG_PATH)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        cfg = _config()
        print(json.dumps({"config": str(CONFIG_PATH), "providers": configured_providers(), "baseUrls": {p: resolve_base_url(None, p) for p in ("openai-image", "gemini", "openai-chat")}, "legacyConfig": "apiKey" in cfg}, ensure_ascii=False, indent=2))
        return 0
    if args.command != "generate":
        parser.print_help()
        return 1

    args.model = args.model or default_model(args.provider)
    api_key = resolve_api_key(args.api_key, args.provider)
    if not api_key:
        print(f"ERROR: missing API key. Run: {sys.argv[0]} setkey --provider {args.provider} '<key>'", file=sys.stderr)
        return 2

    try:
        if args.provider == "gemini":
            obj, b64, mime = generate_gemini(args, api_key)
        elif args.provider == "openai-chat":
            obj, b64, mime = generate_openai_chat(args, api_key)
        else:
            obj, b64, mime = generate_openai_image(args, api_key)
        output = write_image(args.output, b64, mime, args.output_format)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    result = {
        "ok": True,
        "path": str(output),
        "provider": args.provider,
        "model": args.model,
        "size": args.size if args.provider == "openai-image" else None,
        "mime": mime,
        "revised_prompt": _extract_revised_prompt(obj),
        "usage": obj.get("usage") or obj.get("usageMetadata"),
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
