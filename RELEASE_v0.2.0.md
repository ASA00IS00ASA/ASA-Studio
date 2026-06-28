# ASA-Studio v0.2.0

> AI 图像生成 Android 应用 — 文生图 · 图生图 · 4 服务商 · 自包含引擎 · 无需电脑

---

## 下载

[**ASA-Studio-v0.2.0.apk**](https://github.com/ASA00IS00ASA/ASA-Studio/releases/download/v0.2.0/ASA-Studio-v0.2.0.apk) *(7.6 MB)*

> 仅支持 Android 8.0+ | Debug 签名，安装时选「信任此来源」即可

---

## 功能

- **文生图** — 输入画面描述，AI 一键生成图片
- **图生图** — 上传参考图 + 文字描述，生成变体
- **4 大服务商** — OpenAI 兼容 / DALL·E / 阿里百炼通义万象 / Stability AI
- **自包含引擎** — API 调用内置于 App，无需电脑中转，手机直连 AI 服务商
- **150 条精选热词** — 15 个分类每日随机轮换，一键点击使用
- **预设关键词** — 风格 / 画质 / 场景 / 光影分组，点击拼装 prompt
- **8 种画面比例** — 1:1 / 4:3 / 3:4 / 16:9 / 9:16 / 3:2 / 2:3 / 21:9
- **三模式 UI** — 简洁 / 炫酷（粒子交互）/ Hack（CRT 终端美学）
- **历史记录** — 生成图片自动存档，保存到系统相册
- **竖屏优化** — 侧边栏抽屉、全屏设置面板、触控友好布局

---

## 使用

1. 安装 APK，打开 App
2. 点击右上角齿轮 ⚙ → 选择服务商 → 填入 API Key → 保存并测试
3. 输入画面描述 → 点击「生成图像」
4. 图片生成后点击下载保存到相册

---

## 技术架构

```
Android App (WebView + Kotlin)
├── WebView 前端 (HTML/CSS/JS)
│   ├── Glassmorphism / Neon / CRT 三模式 UI
│   ├── Canvas 粒子交互系统
│   └── localStorage 设置持久化
├── Kotlin 引擎 (ApiHandler.kt)
│   ├── OpenAI 兼容 → OkHttp → chat/completions → 解析 Markdown 图片 URL
│   ├── OpenAI DALL·E → images/generations → Base64
│   ├── DashScope 百炼 → 异步任务 → 轮询 → 下载结果
│   └── Stability AI → multipart/form-data → 返回 PNG
└── JavaScript Bridge
    ├── generateImage() → Kotlin 协程 → API 调用 → 回调
    ├── testConnection() → 连接测试
    └── saveImage() → MediaStore 写入系统相册
```

---

## 更新日志

### v0.2.0

- **Android 应用** — 首个移动端版本，内置 AI 调用引擎
- **自包含** — 无需 PC 服务器，手机独立运行
- **三模式 UI** — 简洁 / 炫酷（星空 + 粒子系统）/ Hack（CRT 终端美学）
- **粒子交互系统** — Canvas 实时渲染，鼠标/触摸排斥 + 连线 + 点击爆炸
- **热词引擎** — 150 条精选提示词 + CivitAI 在线抓取（自动降级）
- **移动端竖屏适配** — 抽屉侧边栏、全屏 Modal、触控优化
- **AI 生成图标** — 霓虹六边形水晶 App 图标

---

**100% AI 生成代码 · Claude Code + DeepSeek V4 Pro**
