---
name: visual-studio
description: 视觉工作室。Use when the user asks to generate images via Opus / gpt-image-2 direct API, Gemini 3 Pro Preview / vivgrid, Gemini chat-completions image generation, says “用 opus 画图”, “用 gpt-image-2 直连画图”, “用 Gemini 画图”, “视觉工作室”, or wants image generation without OpenClaw's built-in image_generate fallback behavior. Generates images by calling a configured image provider and returns a local image path for channel-aware delivery.
---

# 视觉工作室 / Visual Studio

Use this skill when the user explicitly asks to use **视觉工作室**, **VS**, **visual-studio**, **opus**, **gpt-image-2 直连**, **Gemini 3 Pro Preview / vivgrid**, or **Gemini chat-completions image generation** for image generation.

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

Set `--size` only when the user requested a concrete supported size. Use `--provider gemini-chat` for Gemini image generation via `/v1/chat/completions`; keep `--provider vivgrid-image` only for `/v1/images/generations` tests.

## API key

This skill uses its own private config only:

```text
~/.openclaw/visual-studio/config.json
```

It must not read or modify OpenClaw model/provider config or auth profiles.

Set keys per provider:

```bash
python3 scripts/opus_image.py setkey --provider openai-image '<opus-api-key>'
python3 scripts/opus_image.py setkey --provider vivgrid-image '<vivgrid-or-opus-api-key>'
python3 scripts/opus_image.py setkey --provider gemini-chat '<vivgrid-or-opus-api-key>'
python3 scripts/opus_image.py setkey --provider gemini-native '<vivgrid-or-opus-api-key>'
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

## Gemini 3 Pro Preview / vivgrid

Gemini native relay endpoint from NewAPI docs (`/v1beta/models/{model}:generateContent/`):

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider gemini-native \
  --model gemini-2.5-flash-image \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-native-$(date +%Y%m%d-%H%M%S).png
```

OpenAI chat relay endpoint (`/v1/chat/completions`):

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider gemini-chat \
  --model gemini-3.1-pro-preview \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-chat-$(date +%Y%m%d-%H%M%S).png
```

Legacy image-generation endpoint (`/v1/images/generations`, currently may reject non-Imagen models):

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider vivgrid-image \
  --model gemini-3.1-pro-preview \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-vivgrid-$(date +%Y%m%d-%H%M%S).png
```

`gemini-native` defaults to the verified image model `gemini-2.5-flash-image` and follows the NewAPI Gemini native docs: `contents` plus `generationConfig.responseModalities`. The docs also show optional `generationConfig.imageConfig.aspectRatio/imageSize`, but the current relayed `gemini-3.1-pro-preview` rejects inferred aspect ratios, so this script does not send imageConfig by default. `gemini-chat` follows the OpenAI chat-format relay docs: `model`, `stream`, `messages`, Gemini-native `contents`, and optional `extra_body`. `gemini-native` uses base URL `https://opus.qzz.io` by default; smoke tests showed `gemini-2.5-flash-image` returns native image data, while `gemini-3-pro-preview` / `gemini-3.1-pro-preview` may return external image URLs for simple prompts and text-only responses for complex prompts; `gemini-chat` / `vivgrid-image` use `https://opus.qzz.io/v1`. If the key is saved with `setkey`, omit `--api-key`.

## Delivery

Delivery is channel-aware:

- **Kimi / `kimi-claw`**: do **not** reply with a `MEDIA:` line for Visual Studio output. Kimi may double-render VS image files when delivered by `MEDIA:`. Send exactly one local image attachment with the `message` tool (`action=send`, `channel=kimi-claw`, `target=main`, `media=<absolute image path>`, `mimeType=image/png` or the real MIME type) and then finish the assistant turn with only `NO_REPLY`. For `gemini-chat`, the API may return an image URL; the script downloads it first, and Kimi delivery must still use the downloaded local file as the image attachment, never the remote URL.
- **Other channels / web UI**: reply with one `MEDIA:/absolute/path.png` line.

Never use both `MEDIA:` and a `message` attachment for the same generated image.
