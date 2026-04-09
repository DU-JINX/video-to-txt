# video-to-txt

批量将视频/音频文件转录为简体中文文本。

基于 [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 实现，支持 GPU 加速，输出自动繁转简，支持断点续跑。

---

## 功能

- 递归扫描指定目录下的所有视频/音频文件
- 调用 Whisper 模型自动语音识别
- 输出结果自动转换为简体中文
- 进度持久化，中断后重新运行自动跳过已完成文件
- 支持 CPU / GPU 两种运行模式

## 支持格式

`.mp4` `.mp3` `.mov` `.avi` `.mkv` `.flv` `.wmv`

---

## 安装

**前置要求：**

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html)（需加入系统 PATH）

**安装依赖：**

```bash
pip install -r requirements.txt
```

---

## 使用

### 基本用法

```bash
python batch_runner.py --nas-root "D:\Videos\我的课程" --output-base "D:\Outputs"
```

### 完整参数

```bash
python batch_runner.py \
  --nas-root    "D:\Videos\我的课程" \   # 视频源目录
  --output-base "D:\Outputs" \           # 输出目录（默认 ./outputs/final）
  --whisper-model small \                # 模型大小：tiny / base / small / medium / large-v3
  --whisper-device cuda \                # 推理设备：auto / cpu / cuda
  --whisper-compute-type float16 \       # 计算精度：int8 / float16
  --language zh \                        # 识别语言
  --dry-run                              # 只扫描，不转录
```

### 没有显卡的机器

```bash
python batch_runner.py --nas-root "D:\Videos" --whisper-device cpu --whisper-compute-type int8
```

---

## 输出结构

```
outputs/
├── final/          # 最终简体中文文本（含元数据）
├── raw/            # 原始转写文本（备份）
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

## 文件说明

| 文件 | 说明 |
|------|------|
| `batch_runner.py` | 批量处理入口 |
| `video_to_text_standalone.py` | 核心转录脚本 |
| `scanner.py` | 视频文件扫描 |
| `transcriber.py` | 转录调用封装 |
| `progress.py` | 进度管理 |
| `converter.py` | 繁简转换工具 |
