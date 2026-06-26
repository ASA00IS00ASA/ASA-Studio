---
name: asa-studio
description: ASA-Studio AI image generation platform development, debugging, and feature iteration
---

# ASA-Studio Skill

This skill provides context and guidance for working on ASA-Studio, an AI-powered image generation web platform.

## Project Overview

ASA-Studio is a FastAPI + vanilla HTML/CSS/JS web app that calls multiple AI image generation providers through their APIs.

## Architecture

```
Server (FastAPI)          Frontend (SPA)
server.py                 static/index.html
├── /api/providers  ────> Provider selector
├── /api/generate   ────> Image generation
├── /api/test       ────> Connection test
├── /api/trending   ────> Daily trending prompts
├── /api/history    ────> Image history
├── /api/alive      ────> Auto-shutdown cancel
├── /api/shutdown   ────> Auto-shutdown trigger
└── / (static mount)
```

## Supported Providers

| Provider ID | Name | API Style | Models |
|-------------|------|-----------|--------|
| `openai-compatible` | OpenAI Compatible (Right Code) | Chat API → image URLs in markdown | nano-banana, gpt-image-2, etc. |
| `openai` | OpenAI DALL·E | Native Images API | dall-e-3, dall-e-2 |
| `dashscope` | 阿里百炼 通义万象 | DashScope async task API | wanx2.0-t2i-turbo, etc. |
| `stability` | Stability AI | REST multipart form | SD XL, SD3.5 |

## Provider Architecture

Each provider has two functions in `server.py`:
- `generate_<provider>(req)` — handles image generation
- `test_<provider>(req)` — tests connection

Registered in `GENERATORS` and `TESTERS` dicts.

## Common Tasks

### Adding a new provider

1. Add entry to `PROVIDERS` dict in `server.py`
2. Implement `generate_<provider>()` and `test_<provider>()`
3. Register in `GENERATORS` and `TESTERS`
4. Add to `PROVIDER_DATA` in `index.html` JavaScript
5. Add to provider select `<option>` in `index.html`

### Adding new trending prompts

Add entries to `TRENDING_PROMPTS` list in `server.py`. Format:
```python
{"zh": "中文提示词", "en": "English prompt", "cat": "分类名"}
```

### Changing the UI theme

All colors are CSS variables in `:root` and `[data-theme="light"]`. Update variables to change both themes simultaneously.

### Debugging API issues

- Server logs go to stdout (uvicorn terminal)
- Check `logger.info()` calls in `server.py` for request/response details
- Use `/api/test` endpoint for connectivity checks
- Frontend errors are displayed in the `#errorMsg` element

## File Structure

```
image-gen-app/
├── server.py              # FastAPI backend (all endpoints + providers)
├── static/index.html      # Complete frontend (CSS + HTML + JS)
├── output/                # Generated images (gitignored)
├── requirements.txt       # Python deps
├── start.bat              # Windows launcher
├── README.md              # Project readme
└── RELEASE_NOTES_vX.X.X.md  # Per-version release notes
```

## Key Conventions

- API keys stored per-provider in localStorage: `asastudio_key_<provider>`
- Theme preference: `asastudio_theme` (dark/light/system)
- Trending toggle: `asastudio_trending` (true/false)
- Version tags follow SemVer: `v MAJOR.MINOR.PATCH`
- Release notes named: `RELEASE_NOTES_vX.X.X.md`
- ZIP packaging via: `git archive --format=zip --output "ASA-Studio_vX.X.X.zip" HEAD`
