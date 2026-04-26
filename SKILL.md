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
