# video-to-txt

批量将视频/音频文件转录为简体中文文本，同时提供 HTTP 转写微服务接口。

基于 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 实现，支持 GPU 加速，输出自动繁转简，支持断点续跑。

---

## 功能

- 递归扫描指定目录下的所有视频/音频文件
- 支持 NAS 挂载目录 / 本地目录 / URL 列表三种输入模式
- 调用 Whisper 模型自动语音识别
- 输出结果自动转换为简体中文
- 进度持久化，中断后重新运行自动跳过已完成文件
- 支持 CPU / GPU 两种运行模式
- 提供 HTTP 微服务接口，供外部系统（如 Java 后端）调用

## 支持格式

`.mp4` `.mp3` `.mov` `.avi` `.mkv` `.flv` `.wmv`

---

## 安装

### 前置依赖

| 依赖 | 说明 | 安装方式 |
|------|------|----------|
| Python 3.10+ | 运行环境 | [python.org](https://www.python.org/downloads/) |
| ffmpeg | 视频/音频解码 | [ffmpeg.org](https://ffmpeg.org/download.html)，需加入系统 PATH |
| CUDA（可选） | GPU 加速 | 安装 NVIDIA 驱动 + CUDA Toolkit 11.x / 12.x |

### Python 包依赖

**CPU 版本：**

```bash
pip install -r requirements.txt
```

**GPU 版本：**

```bash
pip install -r requirements-gpu.txt
```

---

## 使用

### 批量转写（CLI）

```bash
python batch_runner.py \
  --source-mode local \
  --input-dir  "/path/to/videos" \
  --output-base "./outputs/final" \
  --whisper-model small \
  --whisper-device auto \
  --language zh
```

**source-mode 可选值：**

| 值 | 说明 |
|----|------|
| `local` | 本地目录 |
| `nas` | NAS 挂载目录 |
| `url` | URL 列表文件（每行一个，`#` 开头为注释） |

**完整参数：**

```
--source-mode       输入源类型（必填）: local / nas / url
--input-dir         local/nas 模式的视频根目录
--url-file          url 模式的 URL 列表文件路径
--output-base       输出根目录（默认 ./outputs/final）
--whisper-model     模型大小: tiny / base / small / medium / large-v3（默认 small）
--whisper-device    推理设备: auto / cpu / cuda（默认 auto）
--whisper-compute-type  计算精度: auto / int8 / float16（默认 auto）
--language          识别语言（默认 zh）
--dry-run           只扫描来源，不执行转写
--exclude           排除的目录名（可多个）
```

### HTTP 微服务

启动服务：

```bash
bash start_server.sh
```

或 Windows：

```bat
start_server.bat
```

默认监听 `0.0.0.0:8765`，可通过环境变量覆盖：

```bash
TRANSCRIBE_PORT=9000 bash start_server.sh
```

**接口：`POST /api/transcribe`**

```json
{
  "url": "https://example.com/video.mp4",
  "title": "视频标题（可选）",
  "language": "zh",
  "whisperModel": "small"
}
```

响应：

```json
{
  "ok": true,
  "title": "视频标题",
  "text": "转写后的文本内容...",
  "error": ""
}
```

**接口：`GET /health`**

```json
{"status": "ok"}
```

---

## 输出结构

```
outputs/
├── final/              # 最终简体中文文本
├── raw/                # 原始转写文本（备份）
├── audio_cache/        # 音频提取缓存
└── logs/
    └── progress.json   # 进度记录，用于断点续跑
```

---

## 模型选择参考

| 模型 | 速度 | 准确率 | 推荐场景 |
|------|------|--------|----------|
| tiny | 最快 | 一般 | 快速预览 |
| base | 快 | 较好 | 日常使用 |
| small | 中等 | 好 | 推荐默认 |
| medium | 慢 | 很好 | 高质量需求 |
| large-v3 | 最慢 | 最好 | 高精度场景 |

---

## 项目结构

```
video-to-txt/
├── video_to_txt/                   # 核心包
│   ├── core/
│   │   ├── transcriber.py          # 转写入口（调用 standalone 脚本）
│   │   └── chunk_transcriber.py    # 分块独立进程转录
│   ├── io/
│   │   ├── scanner.py              # 目录媒体文件扫描
│   │   ├── source_resolver.py      # 多模式输入源解析
│   │   └── progress.py             # 进度持久化
│   └── utils/
│       └── converter.py            # 繁简体转换
├── api/                            # HTTP 服务层
│   ├── models.py                   # Pydantic 请求/响应模型
│   └── routes.py                   # FastAPI 路由
├── video_to_text_standalone.py     # 核心转录脚本（独立 CLI）
├── server.py                       # HTTP 服务启动入口
├── batch_runner.py                 # 批量转写 CLI 入口
├── start_server.sh                 # Linux/macOS 启动脚本
├── start_server.bat                # Windows 启动脚本
├── requirements.txt                # CPU 版依赖
└── requirements-gpu.txt            # GPU 版依赖
```
