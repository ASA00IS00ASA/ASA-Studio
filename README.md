# ASA-Studio

AI 图像生成平台 — 支持文生图、图生图、风格迁移，内置每日热门提示词，通过中转 API 调用多模型。

---

## 功能

| 功能 | 说明 |
|------|------|
| 文生图 | 输入文字描述，一键生成图片 |
| 图生图 | 上传参考图 + 描述，生成变体或风格迁移 |
| 预设关键词 | 点击风格/画质/场景标签快速组合 prompt |
| 今日热门提示词 | 每日从 36 条精选提示词中轮换 12 条，点击即用 |
| 多模型切换 | nano-banana / gpt-image-2 等 5 种模型 |
| 多比例输出 | 1:1、4:3、16:9、21:9 等 8 种比例 |
| 历史记录 | 自动保存生成的图片，点击回看 |
| 一键下载 | PNG 格式直接下载到本地 |
| 毛玻璃 UI | 深色主题 + Glassmorphism + 动效背景 |

---

## 快速开始

### 环境要求

- Python 3.10+
- 中转 API Key（如 Right Code）

### 安装

```bash
cd image-gen-app
pip install -r requirements.txt
```

### 启动

**方式一：双击启动**

双击 `start.bat`，自动安装依赖、启动服务、打开浏览器。

**方式二：命令行**

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

打开浏览器访问 **http://localhost:8000**

### 配置 API

在左侧栏「API 设置」中填写：

| 字段 | 值 |
|------|-----|
| API Base URL | `https://www.right.codes/draw/v1` |
| API Key | `sk-xxxxxxxx` |

点击「保存设置」→「测试连接」确认连通后即可使用。

---

## 使用指南

### 文生图

1. 在输入框描述想要的画面（中英文均可）
2. 点击预设标签添加风格、画质关键词
3. 选择模型和画面比例
4. 点击「生成图像」或按 `Enter`

### 图生图

1. 点击或拖拽上传参考图
2. 输入描述（如"保持构图，改为水墨风格"）
3. 点击生成

### 热门提示词

标题下方「今日热门提示词」区域，点击任意卡片自动填入 prompt。每日自动轮换不同组合。

---

## 项目结构

```
image-gen-app/
├── server.py           # FastAPI 后端
├── static/
│   └── index.html      # 前端 UI
├── output/             # 生成图片存档
├── requirements.txt    # Python 依赖
└── start.bat           # Windows 一键启动脚本
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/generate` | 生成图片（文生图 / 图生图） |
| POST | `/api/test` | 测试 API 连接 |
| GET | `/api/trending` | 获取今日热门提示词 |
| GET | `/api/history` | 获取历史记录 |
| GET | `/api/image/{filename}` | 获取历史图片 |

---

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python / FastAPI |
| 前端 | 原生 HTML + CSS + JavaScript |
| AI SDK | OpenAI Python SDK（兼容接口） |
| HTTP | httpx |
| UI | Glassmorphism + CSS Animations |

---

## 兼容性

本项目通过 OpenAI 兼容接口调用 AI 模型，支持任意符合 OpenAI API 格式的中转服务：

- Right Code
- 其他兼容 `/v1/chat/completions` 和 `/v1/images/generations` 的中转商

---

## License

MIT
