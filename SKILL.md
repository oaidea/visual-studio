---
name: visual-studio
description: 视觉工作室。Use when the user asks to generate images via Opus / gpt-image-2 direct API, Gemini 2.5 Flash Image, Gemini 3 Flash Preview / vivgrid, says “用 opus 画图”, “用 gpt-image-2 直连画图”, “用 Gemini 画图”, “视觉工作室”, or wants image generation without OpenClaw's built-in image_generate fallback behavior. Generates images by calling a configured image provider and returns a local image path for channel-aware delivery.
---

# 视觉工作室 / Visual Studio

Use this skill when the user explicitly asks to use **视觉工作室**, **VS**, **visual-studio**, **opus**, **gpt-image-2 直连**, **Gemini 2.5 Flash Image**, or **Gemini 3 Flash Preview / vivgrid** for image generation.

## Core rules

- Do **not** use OpenClaw's built-in `image_generate` for this workflow.
- Pass the user's image prompt to the script **verbatim**. Do not rewrite, polish, translate, summarize, or expand it before calling the script.
- Use the bundled script:

```bash
python3 scripts/opus_image.py generate \
  --provider openai-image \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-YYYYMMDD-HHMMSS.png \
  --size 1024x1024
```

Set `--size` only when the user requested a concrete supported size. Use `--provider gemini` for Google's native `/v1beta/models/gemini-2.5-flash-image:generateContent` endpoint. Use `--provider openai-chat` only when a Gemini-compatible service exposes `/v1/chat/completions`.

## API key

This skill uses its own private config only:

```text
~/.openclaw/visual-studio/config.json
```

It must not read or modify OpenClaw model/provider config or auth profiles.

Set keys per provider:

```bash
python3 scripts/opus_image.py setkey --provider openai-image '<opus-api-key>'
python3 scripts/opus_image.py setkey --provider gemini '<google-or-gemini-api-key>'
python3 scripts/opus_image.py setkey --provider openai-chat '<openai-compatible-api-key>' --base-url '<base-url>'
python3 scripts/opus_image.py setkey --provider vivgrid-image '<vivgrid-api-key>' --base-url '<vivgrid-base-url-with-/v1>'
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
  --output /tmp/visual-studio-$(date +%Y%m%d-%H%M%S).png \
  --size 1024x1024
```

Supported defaults:

- model: `gpt-image-2`
- endpoint: `https://opus.qzz.io/v1/images/generations`
- size: `1024x1024`
- output format: `png`
- moderation: `low`
- background: `opaque`

## Gemini 2.5 Flash Image

Native Google endpoint:

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider gemini \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-$(date +%Y%m%d-%H%M%S).png
```

OpenAI-compatible chat endpoint variant:

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider openai-chat \
  --model gemini-2.5-flash-image \
  --base-url '<base-url-with-/v1>' \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-chat-$(date +%Y%m%d-%H%M%S).png
```

## Gemini 3 Flash Preview / vivgrid

Vivgrid image-generation endpoint (`/v1/images/generations`):

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider vivgrid-image \
  --model gemini-3-flash-preview \
  --base-url '<vivgrid-base-url-with-/v1>' \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-vivgrid-$(date +%Y%m%d-%H%M%S).png
```

If the vivgrid key/base URL is saved with `setkey`, omit `--base-url` and `--api-key`.

## Delivery

Delivery is channel-aware:

- **Kimi / `kimi-claw`**: do **not** reply with a `MEDIA:` line for Visual Studio output. Kimi may double-render VS image files when delivered by `MEDIA:`. Instead send exactly one image attachment with the `message` tool (`action=send`, `channel=kimi-claw`, `target=main`, `media=<absolute image path>`, `mimeType=image/png`) and then finish the assistant turn with only `NO_REPLY`.
- **Other channels / web UI**: reply with one `MEDIA:/absolute/path.png` line.

Never use both `MEDIA:` and a `message` attachment for the same generated image.
