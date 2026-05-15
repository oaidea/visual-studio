---
name: visual-studio
description: Generic direct image generation helper skill. Use when the user explicitly asks to use this repository's direct image workflow, wants configurable third-party image generation outside a built-in fallback tool, or needs provider/model/baseUrl controlled image generation with local file output.
---

# Direct Image Generation Helper

Use this skill when the user explicitly asks to use this repository's direct image workflow for configurable third-party image generation.

## Core rules

- Pass the user's image prompt to the script **verbatim**. Do not rewrite, polish, translate, summarize, or expand it before calling the script.
- Default provider/model can be configured. If no default is configured, the script uses `openai-image` with `gpt-image-2`.
- Conversational shorthand: `vs` means use the saved default. `vs:gpt` and `vs:gemini` are single-run overrides only; they do **not** change the saved default.
- Do not store real API keys, real base URLs, or environment-specific values in the repository.
- **Reference images**: Pass `--image <path|url|data-url>` to the generate command. The script handles local files (auto base64), URLs, and data URLs. Model must support it (gpt-image-2 does).
- **Rate limits** (enforced by both `direct_image.py` and `direct_video.py`):

| Type | Per hour | Per day |
|---|---|---|
| Image | 20 | 100 |
| Video | 2 | 5 |

Check usage: `python3 scripts/direct_image.py rate` or `python3 scripts/direct_video.py rate`

## Configuration model

Configuration is stored outside the repository. Recommended structure:

```json
{
  "apiKey": "<default-key>",
  "baseUrl": "<default-base-url>",
  "defaultProvider": "openai-image",
  "defaults": {
    "openai-image": {
      "model": "gpt-image-2"
    },
    "gemini-native": {
      "model": "gemini-2.5-flash-image"
    }
  },
  "providers": {
    "openai-image": {},
    "gemini-native": {
      "baseUrl": "<gemini-base-url-without-v1>"
    }
  }
}
```

Rules:

- Top-level `apiKey` / `baseUrl` are defaults for all providers.
- `providers.<name>.apiKey` / `providers.<name>.baseUrl` override only that provider.
- `defaults.<name>.model` stores the default model for that provider.
- `gemini-native` base URLs should be stored **without** `/v1`; the script normalizes them when saving.

## Conversational flow

### Intent detection — images

When the user sends an image + text in a VS context, determine intent from keywords:

| Keywords in message | Action |
|---|---|
| 生成、画、出图、参考、基于、改成、加上、换成 | → Reference-image generation (`--image`) |
| 看、看看、分析、描述、怎么样、是什么 | → Image analysis (do NOT run VS, use image tool) |
| No image attached, plain text | → Text-to-image generation (no `--image`) |

**One-turn rule**: The user can send the image and intent in the same message. Do NOT split into "save image" then "wait for next message" — process in a single turn when possible.

### Intent detection — videos (WRITTEN IN STONE)

Video generation uses a **strict 3-phase protocol**. The assistant MUST NOT call the video API until Phase 3.

| Phase | Trigger | Assistant Action |
|---|---|---|
| **1. Intent** | Any mention of 视频/拍/做视频/生成视频/seedance | Enter collection mode. Confirm scope (duration, resolution, style). **Do NOT call API.** |
| **2. Collect** | User answers prompts | Ask for each missing parameter: ① content/description ② style (写实/动漫/电影感…) ③ resolution (480p/720p/1080p) ④ duration (4–15s). **Do NOT call API.** Keep asking until all 4 are collected. |
| **3. Execute** | User sends standalone 「生成」 or 「开始生成」 | Assemble parameters, call `direct_video.py generate`, poll, download, deliver. |

**Hard rules (DO NOT BREAK):**
- Never launch video generation without standalone 「生成」 command.
- Even if the user says "生成一个xxx视频" in Phase 1, treat it as intent only — enter collection, do not execute.
- Once all parameters are collected, remind the user: "准备好了，说「生成」就开始～"
- The 「生成」 command must be the user's sole message in that turn (not mixed with other instructions).

### Reference image source resolution — images

When the user wants reference-based generation but doesn't provide a file path:

1. **Chat attachment**: Save the uploaded image to `outputs/_ref_<timestamp>.png`, pass that path to `--image`
2. **URL**: Pass the URL directly to `--image`
3. **Previous output reference** ("用上次那只猫"): Look in `outputs/` for the most recent generated image

## Common commands

Check status:

```bash
python3 scripts/direct_image.py status
```

Reset configuration:

```bash
python3 scripts/direct_image.py reset --yes
```

Initialize one or more providers with verification-before-save:

```bash
python3 scripts/direct_image.py init \
  --target openai \
  --api-key '<api-key>' \
  --base-url '<openai-base-url>'

python3 scripts/direct_image.py init \
  --target gemini \
  --api-key '<api-key>' \
  --base-url '<gemini-base-url-without-v1>'

python3 scripts/direct_image.py init \
  --target both \
  --api-key '<default-api-key>' \
  --base-url '<default-base-url>'
```

Override one provider while keeping top-level defaults:

```bash
python3 scripts/direct_image.py setkey --provider gemini-native '<api-key>'
python3 scripts/direct_image.py setbaseurl --provider gemini-native '<gemini-base-url-without-v1>'
```

Set default model:

```bash
python3 scripts/direct_image.py set-default --provider openai-image --model gpt-image-2
python3 scripts/direct_image.py set-default --provider gemini-native --model gemini-2.5-flash-image
```

Generate with saved default:

```bash
python3 scripts/direct_image.py generate \
  --prompt '<verbatim user prompt>' \
  --output /tmp/direct-image.png
```

Generate with reference image (local file):

```bash
python3 scripts/direct_image.py generate \
  --prompt '<verbatim user prompt>' \
  --image /path/to/reference.png \
  --output /tmp/direct-image-ref.png
```

Generate with reference image (URL):

```bash
python3 scripts/direct_image.py generate \
  --prompt '<verbatim user prompt>' \
  --image 'https://example.com/ref.png' \
  --output /tmp/direct-image-ref.png
```

### Video commands

Check elss.ai connectivity and available video models:

```bash
python3 scripts/direct_video.py status
```

Generate video (DO NOT call directly — only via Phase 3 「生成」):

```bash
python3 scripts/direct_video.py generate \
  --prompt '<verbatim user prompt>' \
  --model seedance-2.0-fast \
  --duration-seconds 5 \
  --resolution 720p \
  --output /tmp/vs-video.mp4
```

Video generation uses an async task model: submit → poll → download. The script handles all three steps.

One-shot provider override:

```bash
python3 scripts/direct_image.py generate \
  --provider vs:gpt \
  --prompt '<verbatim user prompt>' \
  --output /tmp/direct-image-gpt.png \
  --size 1024x1024

python3 scripts/direct_image.py generate \
  --provider vs:gemini \
  --prompt '<verbatim user prompt>' \
  --output /tmp/direct-image-gemini.png
```

## Output contract

Successful runs print localized fields such as:

- `成功`
- `图片路径`
- `提供方`
- `模型`
- `尺寸`
- `返回提示词` (only when actually returned)
- `用量`
- `图片链接` (only when a downloadable URL is returned)

Use the returned local image path for channel-specific delivery.
