# Direct Image Generation Helper

This project provides a local helper for generating images through configurable third-party image providers and returning a local file path for downstream delivery.

## Entry points

| Shortcut | Provider | Default model | Description |
| --- | --- | --- | --- |
| `vs` | saved default | saved default | Use the configured default provider/model |
| `vs:gpt` | `openai-image` | `gpt-image-2` | One-shot override for the OpenAI-style image provider |
| `vs:gemini` | `gemini-native` | `gemini-2.5-flash-image` | One-shot override for the Gemini-style image provider |

Notes:

- `openai-image` typically uses an OpenAI-compatible image endpoint.
- `gemini-native` should be saved and resolved with a base URL **without** `/v1` only for the `https://opus.qzz.io/v1` pattern; in that specific case the script normalizes it when saving.
- When a global default base URL is saved without specifying a provider, the script keeps that value at the top level and automatically writes a Gemini-specific override only for the `https://opus.qzz.io/v1` case.

If no default is configured, the script uses:

```text
openai-image / gpt-image-2
```

Script entry:

```text
python3 scripts/direct_image.py
```

## Configuration structure

Configuration is stored outside the repository and should be supplied by each user for their own environment.

Do not commit real API keys, base URLs, or any environment-specific values into the repository.

Recommended structure: **top-level defaults + provider overrides**

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

- top-level `apiKey` / `baseUrl` = defaults for all providers
- `providers.<name>.apiKey` / `providers.<name>.baseUrl` = provider-specific overrides
- `defaults.<name>.model` = default model for that provider
- missing overrides inherit the top-level defaults

## Initialize and reset

Check current status without revealing secrets:

```bash
python3 scripts/direct_image.py status
```

Reset configuration:

```bash
python3 scripts/direct_image.py reset --yes
```

### Strict initialization

Initialization requires an explicit target:

- `openai`
- `gemini`
- `both`

You can:

- use `--api-key` / `--base-url` as defaults for all selected providers
- override individual providers with:
  - `--openai-key` / `--openai-base-url`
  - `--gemini-key` / `--gemini-base-url`
- initialization verifies connectivity before saving

Initialize openai only:

```bash
python3 scripts/direct_image.py init \
  --target openai \
  --api-key '<api-key>' \
  --base-url '<openai-base-url>'
```

Initialize gemini only:

```bash
python3 scripts/direct_image.py init \
  --target gemini \
  --api-key '<api-key>' \
  --base-url '<gemini-base-url-without-v1>'
```

Initialize both with one default:

```bash
python3 scripts/direct_image.py init \
  --target both \
  --api-key '<default-api-key>' \
  --base-url '<default-base-url>'
```

Initialize both with a gemini-specific base URL:

```bash
python3 scripts/direct_image.py init \
  --target both \
  --api-key '<default-api-key>' \
  --base-url '<default-openai-base-url>' \
  --gemini-base-url '<gemini-base-url-without-v1>'
```

## Set key / base URL

### Apply to all providers by default

Set default key:

```bash
python3 scripts/direct_image.py setkey '<api-key>'
```

Set default base URL:

```bash
python3 scripts/direct_image.py setbaseurl '<base-url>'
```

### Apply to one provider only

Set key for openai only:

```bash
python3 scripts/direct_image.py setkey --provider openai-image '<api-key>'
```

Set key for gemini only:

```bash
python3 scripts/direct_image.py setkey --provider gemini-native '<api-key>'
```

Set base URL for openai only:

```bash
python3 scripts/direct_image.py setbaseurl --provider openai-image '<openai-base-url>'
```

Set base URL for gemini only:

```bash
python3 scripts/direct_image.py setbaseurl --provider gemini-native '<gemini-base-url-without-v1>'
```

Clear default key / base URL:

```bash
python3 scripts/direct_image.py clearkey
python3 scripts/direct_image.py clearbaseurl
```

Clear one provider override:

```bash
python3 scripts/direct_image.py clearkey --provider gemini-native
python3 scripts/direct_image.py clearbaseurl --provider gemini-native
```

## Default models

Set default OpenAI-style image model:

```bash
python3 scripts/direct_image.py set-default \
  --provider openai-image \
  --model gpt-image-2
```

Set default Gemini-style image model:

```bash
python3 scripts/direct_image.py set-default \
  --provider gemini-native \
  --model gemini-2.5-flash-image
```

Notes:

- `vs` uses the saved default
- `vs:gpt` / `vs:gemini` are one-shot overrides only
- `set-default` uses canonical provider names: `openai-image`, `gemini-native`

## Generate images

Use the saved default:

```bash
python3 scripts/direct_image.py generate \
  --prompt '<verbatim prompt>' \
  --output /tmp/direct-image.png
```

One-shot OpenAI-style image generation:

```bash
python3 scripts/direct_image.py generate \
  --provider vs:gpt \
  --prompt '<verbatim prompt>' \
  --output /tmp/direct-image-gpt.png \
  --size 1024x1024
```

One-shot OpenAI-style generation with explicit base URL:

```bash
python3 scripts/direct_image.py generate \
  --provider vs:gpt \
  --base-url '<openai-base-url>' \
  --model gpt-image-2 \
  --prompt '<verbatim prompt>' \
  --output /tmp/direct-image-gpt.png \
  --size 1024x1024
```

One-shot Gemini-style image generation:

```bash
python3 scripts/direct_image.py generate \
  --provider vs:gemini \
  --prompt '<verbatim prompt>' \
  --output /tmp/direct-image-gemini.png
```

## Result output

On success, the script prints localized fields such as:

- `成功`
- `图片路径`
- `提供方`
- `模型`
- `尺寸`
- `返回提示词` (only when the provider actually returns one)
- `用量`
- `图片链接` (only when a downloadable URL is returned)

## Repository safety

Generated images are ignored under:

```text
outputs/
```

Never commit API keys, real base URLs, or environment-specific values into the repository.
