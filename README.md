# SonicVideo

AI 驱动的智能视频剪辑系统 — 基于意图理解和语义匹配，自动将音频、歌词与视觉素材编排为完整的视频作品。

## 功能特性

- **意图驱动剪辑** — 输入剪辑意图（如"热血励志电影混剪"），AI 自动理解并编排分镜
- **语义素材匹配** — CLIP 向量检索 + LLM 深度重排，精准匹配画面与歌词意境
- **Whisper 语音识别** — 自动提取音频中的歌词和时间戳，支持手动歌词校准
- **多模态素材支持** — 视频、图片、HEIC、Apple Live Photo 一键导入
- **实时进度流** — WebSocket 实时推送处理日志和进度
- **原生桌面应用** — pywebview 原生窗口，无需浏览器
- **可配置大模型** — 支持 Qwen/Gemini 模型切换，API Key 和高级参数可视化配置

## 系统要求

- macOS 12+ (Apple Silicon / Intel)
- Python 3.10+
- FFmpeg (`brew install ffmpeg`)
- 8GB+ 内存（推荐 16GB）

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/sonic-video.git
cd sonic-video
```

### 2. 安装依赖

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装 Python 依赖
make install
# 或
pip install -r requirements.txt

# 安装 FFmpeg
brew install ffmpeg
```

### 3. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env，填入 DashScope API Key
```

或在应用内通过设置界面配置。

### 4. 启动

```bash
make dev
# 或
python run.py
```

浏览器打开 `http://localhost:8001`。

### 5. 原生桌面模式

```bash
python launcher.py
```

将打开原生 macOS 窗口。

## DMG 构建

```bash
# 构建 macOS App
make app

# 打包为 DMG
make dmg
```

生成的 DMG 位于 `dist/SonicVideo.dmg`。

## 项目架构

```
sonic-video/
├── app/
│   ├── main.py              # FastAPI 服务 & 流程编排
│   ├── core/
│   │   ├── config_manager.py # 配置管理器
│   │   ├── llm_engine.py     # LLM 引擎 (Qwen/Gemini)
│   │   ├── vector_engine.py  # CLIP 向量检索
│   │   ├── video_processor.py# 场景检测 & 关键帧提取
│   │   ├── editor.py         # 视频合成 & 渲染
│   │   ├── audio_processor.py# Whisper 语音识别
│   │   └── image_processor.py# 图像 & Live Photo 处理
│   └── static/               # 前端资源
├── launcher.py               # 原生桌面入口
├── run.py                    # 开发模式入口
├── setup_app.py              # py2app 构建配置
├── scripts/build_dmg.sh      # DMG 打包脚本
├── Makefile                  # 便捷命令
└── requirements.txt
```

## 处理流程

1. **音频分析** — Whisper 识别歌词 + 时间戳，LLM 对齐校准
2. **素材特征工程** — 场景检测 → 关键帧提取 → CLIP 向量编码
3. **AI 创意编排** — LLM 生成视觉脚本 → CLIP 粗筛 → LLM 深度重排
4. **视频合成** — MoviePy 拼接 + 字幕渲染 + 音轨对齐 + 淡出效果

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| 视频处理 | MoviePy, OpenCV, SceneDetect |
| 语音识别 | OpenAI Whisper |
| 视觉检索 | OpenAI CLIP |
| 大语言模型 | Qwen (DashScope), Gemini |
| 桌面窗口 | pywebview |
| 打包工具 | py2app |

## 配置说明

应用配置保存在 `~/Library/Application Support/SonicVideo/config.json`。

支持以下配置项：
- **API 密钥** — DashScope Key, Gemini Key
- **模型选择** — LLM 模型、Vision 模型、Gemini 模型、CLIP 模型
- **高级参数** — 输出分辨率、FPS、场景检测阈值、最大场景数、并发数、检索 Top-K

所有参数均可通过应用内设置界面修改。

## License

[Apache License 2.0](LICENSE)
