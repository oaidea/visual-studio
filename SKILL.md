---
name: visual-studio
description: 视觉工作室。Use when the user asks to generate images via Opus / gpt-image-2 direct API, says “用 opus 画图”, “用 gpt-image-2 直连画图”, “视觉工作室”, or wants image generation without OpenClaw's built-in image_generate fallback behavior. Generates images by calling an OpenAI-compatible /v1/images/generations endpoint and returns a local image path for MEDIA delivery.
---

# 视觉工作室 / Visual Studio

Use this skill when the user explicitly asks to use **视觉工作室**, **opus**, or **gpt-image-2 直连** for image generation.

## Core rule

Do **not** use OpenClaw's built-in `image_generate` for this workflow. Use the bundled script:

```bash
python3 scripts/opus_image.py --prompt '<prompt>' --output /tmp/opus-image.png
```

Then deliver the generated file with a `MEDIA:/absolute/path.png` line.

## API key

This skill uses its own private config only:

```text
~/.openclaw/visual-studio/config.json
```

It must not read or modify OpenClaw model/provider config or auth profiles.

Set the key:

```bash
python3 scripts/opus_image.py setkey '<opus-api-key>'
```

Clear the key:

```bash
python3 scripts/opus_image.py clearkey
```

Check status without revealing the key:

```bash
python3 scripts/opus_image.py status
```

Prefer not to print or echo the key.

## Typical use

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --prompt '一只可爱盆栽吉祥物，贴纸风格，白色背景' \
  --output /tmp/opus-image.png \
  --size 1024x1024
```

Supported defaults:

- model: `gpt-image-2`
- endpoint: `https://opus.qzz.io/v1/images/generations`
- size: `1024x1024`
- output format: `png`
- moderation: `low`
- background: `opaque`

## Delivery

After successful generation, send:

```text
MEDIA:/tmp/opus-image.png
```
