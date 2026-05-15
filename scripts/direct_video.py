#!/usr/bin/env python3
"""Direct video generation helper for Visual Studio skill (elss.ai seedance)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Rate limiter
_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from rate_limit import check as rate_check, record as rate_record

# Read key and base URL from shared Visual Studio config (outside repo)
_CONFIG_PATH = Path.home() / ".openclaw/visual-studio/config.json"


def _load_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text())
    except Exception:
        return {}


def _api_key() -> str:
    cfg = _load_config()
    key = cfg.get("apiKey", "")
    if not key:
        raise RuntimeError(f"missing apiKey in {_CONFIG_PATH}")
    return key


def _base_url() -> str:
    cfg = _load_config()
    return cfg.get("baseUrl", "https://api.elss.ai/v1").rstrip("/")


DEFAULT_BASE_URL = "https://api.elss.ai/v1"
DEFAULT_OUTPUT = "/tmp/vs-video.mp4"
POLL_INTERVAL = 15
MAX_WAIT = 600


def _post_json(url: str, payload: dict, timeout: int = 30) -> dict:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {_api_key()}",
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


def _get_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {_api_key()}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def submit_task(args: argparse.Namespace) -> str:
    payload = {
        "model": args.model,
        "prompt": args.prompt,
        "duration_seconds": args.duration_seconds,
        "resolution": args.resolution,
    }
    obj = _post_json(f"{_base_url()}/videos", payload, args.timeout)
    task_id = obj.get("id")
    if not task_id:
        raise RuntimeError(f"submit failed: {obj}")
    return task_id


def poll_task(task_id: str, timeout: int) -> dict:
    deadline = time.time() + MAX_WAIT
    while time.time() < deadline:
        obj = _get_json(f"{_base_url()}/videos/{task_id}", timeout)
        status = obj.get("status", "")
        if status in ("succeeded", "completed"):
            return obj
        if status == "failed":
            raise RuntimeError(f"task failed: {obj}")
        time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"task timed out after {MAX_WAIT}s: {task_id}")


def download_video(task_obj: dict, output_path: str) -> Path:
    data = task_obj.get("data")
    url = None
    if isinstance(data, list) and data:
        url = data[0].get("url")
    elif isinstance(data, dict):
        url = data.get("url")
    if not url:
        raise RuntimeError(f"no video URL in task: {json.dumps(task_obj, ensure_ascii=False)[:500]}")

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        content = resp.read()

    out = Path(output_path)
    out.write_bytes(content)
    return out


def generate(args: argparse.Namespace) -> dict:
    # 频率限制检查
    blocked = rate_check("video")
    if blocked:
        raise RuntimeError(f"频率限制 — {blocked['blocked']} 已用 {blocked['used']}/{blocked['limit']}")

    print(f"📤 提交视频任务: {args.model}", file=sys.stderr)
    task_id = submit_task(args)
    print(f"📝 任务 ID: {task_id}", file=sys.stderr)

    print("⏳ 等待渲染...", file=sys.stderr)
    task_obj = poll_task(task_id, args.timeout)

    print("📥 下载视频...", file=sys.stderr)
    output = download_video(task_obj, args.output)

    result = {
        "成功": True,
        "视频路径": str(output),
        "模型": args.model,
        "任务ID": task_id,
        "分辨率": args.resolution,
        "时长_秒": args.duration_seconds,
        "大小": output.stat().st_size,
    }
    usage = task_obj.get("usage")
    if usage:
        result["用量"] = usage
    # 记录用量
    rate_usage = rate_record("video")
    result["频率限制"] = rate_usage
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Visual Studio direct video generation (elss.ai seedance)")
    sub = parser.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="Generate a video")
    gen.add_argument("--prompt", required=True, help="Video description")
    gen.add_argument("--model", default="seedance-2.0-fast", choices=["seedance-2.0", "seedance-2.0-fast"])
    gen.add_argument("--duration-seconds", type=int, default=5, help="Duration in seconds (4-15)")
    gen.add_argument("--resolution", default="720p", choices=["480p", "720p", "1080p"])
    gen.add_argument("--output", default=DEFAULT_OUTPUT, help="Output video path")
    gen.add_argument("--timeout", type=int, default=30, help="HTTP request timeout in seconds")

    sub.add_parser("status", help="Check elss.ai connectivity and models")
    sub.add_parser("rate", help="Show rate limit usage")
    sub.add_parser("help", help="Show this help")

    if len(sys.argv) > 1 and sys.argv[1].startswith("--"):
        sys.argv.insert(1, "generate")

    args = parser.parse_args()

    if args.command == "status":
        try:
            models = _get_json(f"{_base_url()}/models")
            video_models = [m["id"] for m in models.get("data", []) if "seedance" in m.get("id", "").lower()]
            from rate_limit import status as rate_status
            print(json.dumps({
                "ok": True,
                "baseUrl": _base_url(),
                "models": video_models,
                "rateLimits": rate_status(),
            }, ensure_ascii=False, indent=2))
            return 0
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    if args.command == "rate":
        from rate_limit import status as rate_status
        print(json.dumps(rate_status(), ensure_ascii=False, indent=2))
        return 0

    if args.command == "help" or args.command is None:
        parser.print_help()
        return 0

    if args.command != "generate":
        parser.print_help()
        return 1

    try:
        result = generate(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
