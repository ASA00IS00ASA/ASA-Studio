# ASA-Studio

AI 图像生成平台 — 支持文生图、图生图、多服务商、每日热词、深浅色主题。

> **开发方式**：本项目 100% 由 AI 生成代码，使用 **Claude Code** + **DeepSeek V4 Pro** 协作完成。纯 AI 无手工（doge）

---

## 功能

- **文生图** — 输入文字描述，一键生成图片
- **图生图** — 上传参考图 + 描述，生成变体 / 风格迁移
- **多服务商支持** — OpenAI 兼容、DALL·E、阿里百炼 万象、Stability AI
- **每日热门提示词** — 36 条精选提示词每日轮换，点击即用
- **预设关键词** — 风格 / 画质 / 场景分组，点击拼装 prompt
- **多比例输出** — 1:1 / 4:3 / 16:9 / 21:9 等 8 种比例
- **深浅色主题** — 深色 / 浅色 / 跟随系统一键切换
- **历史记录** — 自动存档，点击回看
- **停止生成** — 生成中可随时中止
- **一键启动** — `start.bat` 双击启动，自动打开浏览器
- **关闭网页即退** — 关掉标签页 2 秒后自动停止服务

## 支持的服务商与模型

| 服务商 | 模型 | 图生图 |
|--------|------|--------|
| OpenAI 兼容 (Right Code) | nano-banana, gpt-image-2 等 | ✓ |
| OpenAI DALL·E | dall-e-3, dall-e-2 | ✗ |
| 阿里百炼 通义万象 | wanx2.0, wanx2.1, cosplay | ✓ |
| Stability AI | SD XL, SD3.5 Large/Medium | ✓ |

## 快速开始

```bash
pip install -r requirements.txt
uvicorn server:app --port 8000
```

或双击 `start.bat` 一键启动，访问 http://localhost:8000。

## 项目结构

```
image-gen-app/
├── server.py                     # FastAPI 后端 (多服务商适配)
├── static/
│   └── index.html                # 前端 UI (Glassmorphism + 动效)
├── .claude/skills/
│   └── asa-studio.md             # Claude Code Skill（开发辅助）
├── output/                       # 生成图片存档
├── requirements.txt              # Python 依赖
├── start.bat                     # Windows 一键启动
├── README.md                     # 项目说明
└── RELEASE_NOTES_vX.X.X.md       # 版本说明
```

## Claude Code Skill

本项目内置了 Claude Code Skill 文件（`.claude/skills/asa-studio.md`），在项目目录下使用 Claude Code 时输入 `/asa-studio` 即可加载项目上下文，包含：

- 架构概览与 API 路由
- 4 家服务商的适配方式
- 添加新服务商的步骤指南
- UI 主题变量结构
- 版本命名与打包规范

## 技术栈

Python · FastAPI · OpenAI SDK · httpx · CSS Animations · Glassmorphism · Claude Code · DeepSeek V4 Pro

---

**纯 AI 无手工（doge）**
