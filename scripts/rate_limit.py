#!/usr/bin/env python3
"""Shared rate limiter for Visual Studio (images + videos)."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

USAGE_PATH = Path.home() / ".openclaw/visual-studio/usage.json"

LIMITS = {
    "image": {"hourly": 20, "daily": 100},
    "video": {"hourly": 2, "daily": 5},
}


def _load() -> dict:
    if USAGE_PATH.exists():
        try:
            return json.loads(USAGE_PATH.read_text())
        except Exception:
            pass
    return {}


def _save(data: dict) -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = USAGE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    os.chmod(tmp, 0o600)
    tmp.replace(USAGE_PATH)


def _now_hour() -> int:
    return int(time.time() / 3600)


def _now_day() -> int:
    return int(time.time() / 86400)


def check(kind: str) -> dict | None:
    """Check rate limit. Returns None if OK, dict with error info if limited."""
    assert kind in ("image", "video"), f"unknown kind: {kind}"
    limits = LIMITS[kind]
    data = _load()
    now_h = _now_hour()
    now_d = _now_day()

    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    # Reset hourly window
    if hourly.get("window") != now_h:
        hourly = {"window": now_h, "image": 0, "video": 0}
        data["hourly"] = hourly

    # Reset daily window
    if daily.get("window") != now_d:
        daily = {"window": now_d, "image": 0, "video": 0}
        data["daily"] = daily

    count_h = hourly.get(kind, 0)
    count_d = daily.get(kind, 0)

    # Check hourly
    if count_h >= limits["hourly"]:
        return {"blocked": "hourly", "kind": kind, "used": count_h, "limit": limits["hourly"],
                "重置": "下一小时", "usedDaily": count_d, "limitDaily": limits["daily"]}

    # Check daily
    if count_d >= limits["daily"]:
        return {"blocked": "daily", "kind": kind, "used": count_d, "limit": limits["daily"],
                "重置": "明天", "usedHourly": count_h, "limitHourly": limits["hourly"]}

    return None


def record(kind: str, count: int = 1) -> dict:
    """Record usage after successful generation."""
    assert kind in ("image", "video"), f"unknown kind: {kind}"
    data = _load()
    now_h = _now_hour()
    now_d = _now_day()

    hourly = data.get("hourly", {})
    if hourly.get("window") != now_h:
        hourly = {"window": now_h, "image": 0, "video": 0}
    hourly[kind] = hourly.get(kind, 0) + count

    daily = data.get("daily", {})
    if daily.get("window") != now_d:
        daily = {"window": now_d, "image": 0, "video": 0}
    daily[kind] = daily.get(kind, 0) + count

    data["hourly"] = hourly
    data["daily"] = daily
    _save(data)

    limits = LIMITS[kind]
    return {
        "hourly": {"used": hourly[kind], "limit": limits["hourly"]},
        "daily": {"used": daily[kind], "limit": limits["daily"]},
    }


def status() -> dict:
    """Show current usage without modifying."""
    data = _load()
    now_h = _now_hour()
    now_d = _now_day()

    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    if hourly.get("window") != now_h:
        hourly = {"window": now_h, "image": 0, "video": 0}
    if daily.get("window") != now_d:
        daily = {"window": now_d, "image": 0, "video": 0}

    return {
        "hourly": {"image": {"used": hourly.get("image", 0), "limit": LIMITS["image"]["hourly"]},
                   "video": {"used": hourly.get("video", 0), "limit": LIMITS["video"]["hourly"]}},
        "daily": {"image": {"used": daily.get("image", 0), "limit": LIMITS["image"]["daily"]},
                  "video": {"used": daily.get("video", 0), "limit": LIMITS["video"]["daily"]}},
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"usage": USAGE_PATH, "limits": LIMITS, "current": status()}, ensure_ascii=False, indent=2))
