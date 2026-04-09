from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def transcribe(
    video_path: str,
    output_dir: str,
    *,
    model: str = 'small',
    device: str = 'cuda',
    compute_type: str = 'float16',
    language: str = 'zh',
    dry_run: bool = False,
) -> dict:
    """调用 standalone 脚本转写单个视频, 返回结果 dict."""
    script = Path(__file__).parent / 'video_to_text_standalone.py'
    raw_dir = Path('outputs/raw').resolve()
    cmd = [
        sys.executable, '-X', 'utf8', str(script),
        video_path,
        '--output-dir', output_dir,
        '--raw-dir', str(raw_dir),
        '--whisper-model', model,
        '--whisper-device', device,
        '--whisper-compute-type', compute_type,
        '--language', language,
    ]
    if dry_run:
        cmd.append('--dry-run')

    # 强制子进程 UTF-8 输出, 避免 Windows GBK 解码失败
    # 同时将 ffmpeg bin 目录注入 PATH, 防止子进程找不到 ffprobe
    ffmpeg_bin = (
        r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Packages'
        r'\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe'
        r'\ffmpeg-8.1-full_build\bin'
    )
    cuda_bin = r'C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin'
    extra = [ffmpeg_bin, cuda_bin]
    path = os.environ.get('PATH', '')
    for p in extra:
        if p not in path:
            path = p + os.pathsep + path
    env = {**os.environ, 'PYTHONUTF8': '1', 'PATH': path}
    # stdout 捕获用于 JSON 解析, stderr 直接透传到终端显示进度条
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None, env=env)
    stdout_bytes, _ = proc.communicate()
    stdout = stdout_bytes.decode('utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(stdout or f'exit code {proc.returncode}')
    return json.loads(stdout)
