#!/usr/bin/env python3
"""Direct Opus/gpt-image-2 image generation helper for Visual Studio skill."""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://opus.qzz.io/v1"
DEFAULT_MODEL = "gpt-image-2"
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


def set_api_key(api_key: str, base_url: str = DEFAULT_BASE_URL) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("empty API key")
    _write_private_json(CONFIG_PATH, {"apiKey": key, "baseUrl": base_url.rstrip("/")})


def clear_api_key() -> bool:
    if CONFIG_PATH.exists():
        CONFIG_PATH.unlink()
        return True
    return False


def resolve_api_key(explicit: str | None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    cfg = _load_json(CONFIG_PATH) or {}
    key = cfg.get("apiKey")
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


def resolve_base_url(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip().rstrip("/")
    cfg = _load_json(CONFIG_PATH) or {}
    base_url = cfg.get("baseUrl")
    if isinstance(base_url, str) and base_url.strip():
        return base_url.strip().rstrip("/")
    return DEFAULT_BASE_URL


def post_json(url: str, api_key: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body[:2000]}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Visual Studio direct Opus/gpt-image-2 helper")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate an image")
    gen.add_argument("--prompt", required=True, help="Image prompt")
    gen.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path")
    gen.add_argument("--size", default=DEFAULT_SIZE, help="Image size, e.g. 1024x1024")
    gen.add_argument("--model", default=DEFAULT_MODEL, help="Model id")
    gen.add_argument("--base-url", default=None, help="OpenAI-compatible base URL")
    gen.add_argument("--api-key", default=None, help="One-shot API key; not saved")
    gen.add_argument("--timeout", type=int, default=240, help="Request timeout seconds")
    gen.add_argument("--background", default="opaque", choices=["opaque", "transparent", "auto"])
    gen.add_argument("--moderation", default="low", choices=["low", "auto"])
    gen.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    gen.add_argument("--count", type=int, default=1)

    setkey = sub.add_parser("setkey", help="Save API key to Visual Studio private config")
    setkey.add_argument("key", help="Opus API key")
    setkey.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL to save")

    sub.add_parser("clearkey", help="Delete saved Visual Studio API key")
    sub.add_parser("status", help="Show whether key is configured without revealing it")

    # Backward compatibility: allow old --prompt ... invocation as generate.
    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.argv.insert(1, "generate")

    args = parser.parse_args()

    if args.command == "setkey":
        set_api_key(args.key, args.base_url)
        print(json.dumps({"ok": True, "config": str(CONFIG_PATH), "baseUrl": args.base_url.rstrip("/")}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "clearkey":
        removed = clear_api_key()
        print(json.dumps({"ok": True, "removed": removed, "config": str(CONFIG_PATH)}, ensure_ascii=False, indent=2))
        return 0
    if args.command == "status":
        cfg = _load_json(CONFIG_PATH) or {}
        print(json.dumps({"configured": bool(resolve_api_key(None)), "config": str(CONFIG_PATH), "baseUrl": cfg.get("baseUrl")}, ensure_ascii=False, indent=2))
        return 0
    if args.command != "generate":
        parser.print_help()
        return 1

    api_key = resolve_api_key(args.api_key)
    if not api_key:
        print(f"ERROR: missing API key. Run: {sys.argv[0]} setkey '<key>'", file=sys.stderr)
        return 2

    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
        "size": args.size,
        "n": args.count,
        "output_format": args.output_format,
        "moderation": args.moderation,
        "background": args.background,
    }
    url = resolve_base_url(args.base_url) + "/images/generations"
    obj = post_json(url, api_key, payload, args.timeout)

    data = obj.get("data") or []
    if not data or not isinstance(data, list):
        print("ERROR: response has no data array", file=sys.stderr)
        print(json.dumps(obj, ensure_ascii=False, indent=2), file=sys.stderr)
        return 3

    first = data[0]
    b64 = first.get("b64_json") if isinstance(first, dict) else None
    if not isinstance(b64, str) or not b64.strip():
        print("ERROR: response has no b64_json", file=sys.stderr)
        print(json.dumps(obj, ensure_ascii=False, indent=2), file=sys.stderr)
        return 4

    if b64.startswith("data:"):
        b64 = b64.split(",", 1)[1]

    output = Path(args.output)
    if output.exists() and output.is_dir():
        output = output / f"opus-image-{int(time.time())}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(b64))

    result = {
        "ok": True,
        "path": str(output),
        "model": args.model,
        "size": args.size,
        "revised_prompt": first.get("revised_prompt") if isinstance(first, dict) else None,
        "usage": obj.get("usage"),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
