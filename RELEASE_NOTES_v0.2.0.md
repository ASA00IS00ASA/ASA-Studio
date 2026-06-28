# ASA-Studio v0.2.0 — UI 三模式 · 粒子系统 · CRT 终端美学

## 新增功能

### 三模式 UI 系统
一键切换三种视觉风格，偏好自动记忆：

- **简洁模式** — 原始 Glassmorphism 玻璃拟态设计，紫色渐变标题，深浅色主题
- **炫酷模式** — 星空背景 (CSS box-shadow)、霓虹青/金/粉配色、全局发光效果
- **Hack 模式** — Serial Experiments Lain 风格 CRT 终端美学，详细效果见下

### 粒子交互系统 (Canvas)
- 85 个粒子实时渲染，鼠标移入 130px 范围内粒子被驱散
- 相距 115px 以内的粒子自动连线，越近越亮
- 点击任意位置，200px 范围内粒子向外爆炸
- 炫酷模式（青/金/白/粉调色板）和 Hack 模式（绿色磷光调色板）各自独立配色
- 切回简洁模式时 Canvas 完全销毁，零性能残留

### Hack 模式 — CRT 终端美学
完整复刻 1998 年 Serial Experiments Lain 视觉语言：

| 效果 | 实现方式 |
|------|----------|
| 厚重扫描线 | repeating-linear-gradient 每 4px 暗线 |
| 磷光柔焦 Bloom | 双层 radial-gradient 绿色光晕 + 呼吸动画 |
| CRT 暗角晕影 | radial-gradient 边缘渐变至 85% 黑色 |
| 色散边缘 | 红/蓝渐变在屏幕边缘模拟 CRT 色差 |
| 屏幕门像素栅格 | 3px 绿色点阵颗粒纹理 |
| 快速屏幕闪烁 | 0.08s 间隔 opacity 微颤 |
| 信号干扰条纹 | 水平绿色发光线 + 红蓝伴线横扫屏幕 |
| 标题 RGB 分裂故障 | ::before 伪元素红色克隆层，故障瞬间偏移 |
| 标题闪烁光标 | ::after 绿色 █ 字符 0.8s 闪烁 |
| 终端风格标签 | 所有预设标签自动加 [ ] 方括号 |
| 全局磷光文字 | 所有文字 1px 微绿 text-shadow |

### 热词引擎升级
- 本地精选库从 36 条扩充至 **150 条**，覆盖 15 个分类（爆款/电影感/设计/摄影/插画/3D/时尚/建筑/奇幻/治愈/国风/抽象/游戏/人物/自然）
- 新增 CivitAI API 在线实时热词抓取（1 小时缓存，失败自动降级）
- 新增 ↻ 刷新按钮，一键随机换批

### 炫酷模式视觉
- CSS 纯星空背景 (box-shadow 粒子星场)
- 霓虹渐变标题 + 光晕脉冲
- 青色描边生成按钮 + 金色推荐标签
- 所有控件悬停霓虹发光

## Bug 修复

- 修复炫酷模式 `-webkit-background-clip: text` 标题渲染异常（`background` 简写重置 `background-clip`）
- 修复 `body::after` 伪元素与 Canvas 合成层冲突导致渐变文字消失
- 修复 Chrome `filter: drop-shadow()` + `background-clip: text` 已知兼容性问题

## 技术栈

Python · FastAPI · OpenAI SDK · httpx · HTML5 Canvas API · CSS Animations
CRT Terminal Aesthetic · Glassmorphism · Neon Glow · Particle System

---

**纯 AI 无手工（doge）**

## 升级指南

从 v0.1.0 升级只需替换 `server.py` 和 `static/index.html`，运行 `pip install -r requirements.txt`（依赖无变化）。
