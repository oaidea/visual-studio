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


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def resolve_api_key(explicit: str | None) -> str | None:
    if explicit and explicit.strip():
        return explicit.strip()
    env = os.environ.get("OPUS_API_KEY")
    if env and env.strip():
        return env.strip()

    auth_path = Path.home() / ".openclaw/agents/main/agent/auth-profiles.json"
    auth = _load_json(auth_path)
    profile = (auth or {}).get("profiles", {}).get("openai:opus-qzz")
    key = profile.get("key") if isinstance(profile, dict) else None
    if isinstance(key, str) and key.strip():
        return key.strip()

    cfg_path = Path.home() / ".openclaw/openclaw.json"
    cfg = _load_json(cfg_path)
    key = (((cfg or {}).get("models") or {}).get("providers") or {}).get("openai", {}).get("apiKey")
    if isinstance(key, str) and key.strip():
        return key.strip()
    return None


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
    parser = argparse.ArgumentParser(description="Generate an image via opus.qzz.io gpt-image-2")
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output PNG path")
    parser.add_argument("--size", default=DEFAULT_SIZE, help="Image size, e.g. 1024x1024")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model id")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="OpenAI-compatible base URL")
    parser.add_argument("--api-key", default=None, help="API key; prefer env/auth profile instead")
    parser.add_argument("--timeout", type=int, default=240, help="Request timeout seconds")
    parser.add_argument("--background", default="opaque", choices=["opaque", "transparent", "auto"])
    parser.add_argument("--moderation", default="low", choices=["low", "auto"])
    parser.add_argument("--output-format", default="png", choices=["png", "webp", "jpeg"])
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    api_key = resolve_api_key(args.api_key)
    if not api_key:
        print("ERROR: missing API key. Set OPUS_API_KEY, pass --api-key, or add auth profile openai:opus-qzz.", file=sys.stderr)
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
    url = args.base_url.rstrip("/") + "/images/generations"
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
