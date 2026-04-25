---
name: visual-studio
description: 视觉工作室。Use when the user asks to generate images via Opus / gpt-image-2 direct API, Gemini 2.5 Flash Image native relay, says “用 opus 画图”, “用 gpt-image-2 直连画图”, “用 Gemini 画图”, “视觉工作室”, or wants image generation without OpenClaw's built-in image_generate fallback behavior. Generates images by calling a configured image provider and returns a local image path for channel-aware delivery.
---

# 视觉工作室 / Visual Studio

Use this skill when the user explicitly asks to use **视觉工作室**, **VS**, **visual-studio**, **opus**, **gpt-image-2 直连**, or **Gemini 2.5 Flash Image** for image generation.

## Core rules

- Do **not** use OpenClaw's built-in `image_generate` for this workflow.
- Pass the user's image prompt to the script **verbatim**. Do not rewrite, polish, translate, summarize, or expand it before calling the script.
- Default can be configured. If no default is configured, VS uses `openai-image` (`gpt-image-2`).
- Conversational shorthand: `vs` means use the saved default. `vs:gpt` and `vs:gemini` are single-run overrides only; they do **not** change the saved default.

## API key

This skill uses its own private config only:

```text
~/.openclaw/visual-studio/config.json
```

Set keys per provider:

```bash
python3 scripts/opus_image.py setkey --provider openai-image '<opus-api-key>'
python3 scripts/opus_image.py setkey --provider gemini-native '<opus-or-gemini-relay-api-key>'
```

Check status without revealing keys:

```bash
python3 scripts/opus_image.py status
```

Initialize or validate setup after first install/reset:

```bash
python3 scripts/opus_image.py init
```

If `init` reports `ready: false`, configure at least the current default provider key, then run `init` again.

Reset Visual Studio private config (destructive, requires confirmation):

```bash
python3 scripts/opus_image.py reset --yes
python3 scripts/opus_image.py setkey --provider openai-image '<api-key>'
python3 scripts/opus_image.py init
```

## Defaults and model selection

Set persistent default provider/model:

```bash
python3 scripts/opus_image.py set-default --provider openai-image --model gpt-image-2
python3 scripts/opus_image.py set-default --provider gemini-native --model gemini-2.5-flash-image
# Note: set-default uses canonical provider names, not vs:gpt / vs:gemini.
```

Generate with the saved default:

```bash
python3 scripts/opus_image.py generate \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-$(date +%Y%m%d-%H%M%S).png
```

Temporary override without changing the saved default:

```bash
python3 scripts/opus_image.py generate \
  --provider vs:gemini \
  --model gemini-2.5-flash-image \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-$(date +%Y%m%d-%H%M%S).png \
  --size ''
```

Single-run alias mapping:

```text
vs         -> use saved default
vs:gpt     -> this run only: --provider openai-image --model gpt-image-2
vs:gemini  -> this run only: --provider gemini-native --model gemini-2.5-flash-image
```

## Opus / gpt-image-2

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider openai-image \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-$(date +%Y%m%d-%H%M%S).png \
  --size 1024x1024
```

Defaults:

- model: `gpt-image-2`
- endpoint: `https://opus.qzz.io/v1/images/generations`
- output format: `png`

## Gemini native image

Verified working model: `gemini-2.5-flash-image`.

```bash
python3 /root/.openclaw/workspace/repos/visual-studio/scripts/opus_image.py generate \
  --provider gemini-native \
  --prompt '<verbatim user prompt>' \
  --output /tmp/visual-studio-gemini-native-$(date +%Y%m%d-%H%M%S).png \
  --size ''
```

Implementation follows the NewAPI Gemini native docs:

```text
POST /v1beta/models/{model}:generateContent/
body: contents + generationConfig.responseModalities
```

Do not send inferred `imageConfig.aspectRatio/imageSize` by default; this relay/model may reject aspectRatio even while image generation works without imageConfig.

Removed unstable Gemini 3.x routes: `/v1/images/generations` and `/v1/chat/completions` variants were tested and deleted because they returned text or external URLs inconsistently for complex prompts.

## Delivery

Delivery is channel-aware:

- **Kimi / `kimi-claw`**: do **not** reply with a `MEDIA:` line for Visual Studio output. Kimi may double-render VS image files when delivered by `MEDIA:`. Send exactly one local image attachment with the `message` tool (`action=send`, `channel=kimi-claw`, `target=main`, `media=<absolute image path>`, `mimeType=image/png` or the real MIME type) and then finish the assistant turn with only `NO_REPLY`.
- **Other channels / web UI**: reply with one `MEDIA:/absolute/path.png` line.

Never use both `MEDIA:` and a `message` attachment for the same generated image.
