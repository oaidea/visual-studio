# Visual Studio / 视觉工作室

Visual Studio 是一个本地图片生成辅助项目，用于在 OpenClaw 外部直连图像接口生成图片，并返回本地文件路径，方便按不同渠道交付。

> 这里的 Visual Studio 不是微软 Visual Studio，而是“视觉工作室”。

## 生成入口说明

| 短指令 | Provider | 默认模型 | 说明 |
| --- | --- | --- | --- |
| `vs` | 当前保存的默认 | 当前保存的默认 | 使用配置里的默认 provider/model |
| `vs:gpt` | `openai-image` | `gpt-image-2` | 单次使用图片接口，不改变默认 |
| `vs:gemini` | `gemini-native` | `gemini-2.5-flash-image` | 单次使用图片接口，不改变默认 |

当前默认若未配置，脚本使用：

```text
openai-image / gpt-image-2
```

## 初始化与重置

检查当前配置是否可用：

```bash
python3 scripts/opus_image.py init
```

查看状态（不会打印密钥）：

```bash
python3 scripts/opus_image.py status
```

设置 API key：

```bash
python3 scripts/opus_image.py setkey --provider openai-image '<api-key>'
python3 scripts/opus_image.py setkey --provider gemini-native '<api-key>'
```

重置私有配置：

```bash
python3 scripts/opus_image.py reset --yes
```

私有配置保存于仓库外：

```text
~/.openclaw/visual-studio/config.json
```

不要把 API key 写进仓库文件。

## 默认模型设置

设置默认走 GPT 图片接口：

```bash
python3 scripts/opus_image.py set-default \
  --provider openai-image \
  --model gpt-image-2
```

设置默认走 Gemini 图片接口：

```bash
python3 scripts/opus_image.py set-default \
  --provider gemini-native \
  --model gemini-2.5-flash-image
```

注意：

- `vs` 表示使用当前保存的默认。
- `vs:gpt` / `vs:gemini` 只表示单次指定，不改变默认。
- `set-default` 使用正式 provider 名：`openai-image` 或 `gemini-native`。

## 生成图片

使用当前默认：

```bash
python3 scripts/opus_image.py generate \
  --prompt '<原样提示词>' \
  --output /tmp/visual-studio.png
```

单次指定 GPT 图片接口：

```bash
python3 scripts/opus_image.py generate \
  --provider vs:gpt \
  --prompt '<原样提示词>' \
  --output /tmp/visual-studio-gpt.png \
  --size 1024x1024
```

单次指定 Gemini 图片接口：

```bash
python3 scripts/opus_image.py generate \
  --provider vs:gemini \
  --prompt '<原样提示词>' \
  --output /tmp/visual-studio-gemini.png \
  --size ''
```

## 仓库安全

生成图片输出目录已忽略：

```text
outputs/
```

API key 保存在仓库外，不应提交到 Git。
