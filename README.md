# ASA-Studio v0.2.0

AI 图像生成平台 — 文生图 · 图生图 · 多服务商 · 三模式 UI · 粒子交互 · CRT 终端美学

> **开发方式**：本项目 100% 由 AI 生成代码，使用 **Claude Code** + **DeepSeek V4 Pro** 协作完成。

---

## 功能

- **文生图** — 输入文字描述，一键生成图片
- **图生图** — 上传参考图 + 描述，生成变体 / 风格迁移
- **多服务商支持** — OpenAI 兼容、DALL·E、阿里百炼 万象、Stability AI
- **三模式 UI** — 简洁 / 炫酷 / Hack，一键切换
  - **简洁模式** — 原始 Glassmorphism 玻璃拟态设计
  - **炫酷模式** — 星空背景 + 粒子系统（鼠标驱动散、连线、点击爆炸）+ 霓虹渐变
  - **Hack 模式** — Serial Experiments Lain 风格 CRT 终端美学：绿色磷光、扫描线、CRT 晕影、屏幕闪烁、RGB 分裂故障标题、信号干扰条纹
- **粒子交互系统** — Canvas 粒子与鼠标实时互动，炫酷/Hack 模式双调色板
- **每日热门提示词** — 150 条精选提示词随机轮换，支持 CivitAI 在线热词抓取（需网络可达）
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
| OpenAI 兼容 (Right Code) | nano-banana, nano-banana-2, gpt-image-2, gpt-image-2-vip, nano-banana-pro | ✓ |
| OpenAI DALL·E | dall-e-3, dall-e-2 | ✗ |
| 阿里百炼 通义万象 | wanx2.0-t2i-turbo, wanx2.1-t2i-turbo, wanx2.0-t2i-plus, wanx2.0-cosplay | ✓ |
| Stability AI | stable-diffusion-xl-1024-v1-0, sd3.5-large, sd3.5-medium, core | ✓ |

## 快速开始

```bash
pip install -r requirements.txt
uvicorn server:app --port 8000
```

或双击 `start.bat` 一键启动，访问 http://localhost:8000。

## 项目结构

```
image-gen-app/
├── server.py                     # FastAPI 后端 (多服务商适配 + 热词引擎)
├── static/
│   └── index.html                # 前端 SPA (三模式 UI + 粒子系统 + CRT 效果)
├── .claude/skills/
│   └── asa-studio.md             # Claude Code Skill（开发辅助）
├── output/                       # 生成图片存档
├── requirements.txt              # Python 依赖
├── start.bat                     # Windows 一键启动
└── README.md                     # 项目说明
```

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/providers` | GET | 获取服务商列表及模型 |
| `/api/generate` | POST | 生成图像 |
| `/api/test` | POST | 测试服务商连接 |
| `/api/trending` | GET | 获取每日热门提示词（支持 `?force=1` 强制刷新、`?seed=xxx` 随机排序） |
| `/api/history` | GET | 获取生成历史列表 |
| `/api/image/{filename}` | GET | 获取历史图片 Base64 |
| `/api/alive` | POST | 保持服务存活（取消自动关闭计时） |
| `/api/shutdown` | POST | 触发自动关闭 |

## UI 模式

| 模式 | 配色 | 特色效果 |
|------|------|----------|
| **简洁** | 紫色渐变 + 玻璃拟态 | 基础动效、暗色/亮色/跟随系统 |
| **炫酷** | 青色 #00d4ff + 金色 #fac900 | 星空背景、霓虹发光、粒子连线与鼠标排斥 |
| **Hack** | 绿色磷光 #00ff41 + 琥珀 #ffb000 | CRT 扫描线、磷光 Bloom、色散边缘、屏幕闪烁、标题故障跳动、信号干扰条纹、像素栅格 |

## 热词引擎

- **本地精选**：150 条高质量提示词，覆盖 15 个分类（爆款 / 电影感 / 设计 / 摄影 / 插画 / 3D / 时尚 / 建筑 / 奇幻 / 治愈 / 国风 / 抽象 / 游戏 / 人物 / 自然）
- **在线来源**：尝试从 CivitAI API 获取实时热门 prompt，1 小时缓存，失败自动降级到本地精选
- **刷新换批**：点击 ↻ 按钮或底部来源链接随机换一批提示词

## Claude Code Skill

本项目内置了 Claude Code Skill 文件（`.claude/skills/asa-studio.md`），在项目目录下使用 Claude Code 时输入 `/asa-studio` 即可加载项目上下文，包含：

- 架构概览与 API 路由
- 4 家服务商的适配方式
- 添加新服务商的步骤指南
- 三模式 UI 主题变量结构
- 版本命名与打包规范

## 技术栈

Python · FastAPI · OpenAI SDK · httpx · Canvas API · CSS Animations · Glassmorphism · CRT Terminal Aesthetic · Claude Code · DeepSeek V4 Pro

---

**纯 AI 无手工（doge）**

## Changelog

### v0.2.0
- 新增三模式 UI 切换（简洁 / 炫酷 / Hack）
- 新增 Canvas 粒子交互系统（鼠标排斥、连线、点击爆炸）
- 新增 Hack 模式 CRT 终端美学（扫描线、磷光 Bloom、RGB 分裂故障、信号干扰）
- 新增炫酷模式星空背景 + 霓虹主题
- 热词库从 36 条扩充至 150 条（15 个分类）
- 新增 CivitAI 在线热词抓取（自动降级）
- 新增热词刷新按钮
- 修复炫酷模式标题渲染 bug
- 修复 `body::after` 扫描线导致 `-webkit-background-clip: text` 合成层冲突

### v0.1.0
- 初始版本
- 4 服务商支持 + 文生图 / 图生图
- Glassmorphism UI + 深浅色主题
- 36 条每日轮换提示词
- 自动关闭机制
