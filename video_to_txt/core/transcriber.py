"""调用 video_to_text_standalone.py 完成单视频转写."""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def _build_env() -> dict:
    """构建子进程环境变量，跨平台自动补全 ffmpeg / CUDA 路径."""
    env = {**os.environ, 'PYTHONUTF8': '1'}
    if platform.system() != 'Windows':
        return env

    extra: list[str] = []
    if not shutil.which('ffmpeg'):
        winget_base = Path.home() / 'AppData' / 'Local' / 'Microsoft' / 'WinGet' / 'Packages'
        if winget_base.exists():
            for exe in winget_base.rglob('ffmpeg.exe'):
                extra.append(str(exe.parent))
                break

    cuda_base = Path(r'C:\Program Files\NVIDIA GPU Computing Toolkit')
    if cuda_base.exists():
        # 结构: CUDA/v12.6/bin 或 CUDA/v11.x/bin
        for dll in sorted(cuda_base.rglob('cublas64_*.dll'), reverse=True):
            extra.append(str(dll.parent))
            break

    if extra:
        path = env.get('PATH', '')
        for p in extra:
            if p not in path:
                path = p + os.pathsep + path
        env['PATH'] = path

    return env


def transcribe(
    video_path: str,
    output_dir: str,
    *,
    model: str = 'small',
    device: str = 'auto',
    compute_type: str = 'auto',
    language: str = 'zh',
    dry_run: bool = False,
) -> dict:
    """调用 standalone 脚本转写单个视频或 URL，返回结果 dict."""
    script = Path(__file__).parent.parent.parent / 'video_to_text_standalone.py'
    raw_dir = Path('outputs/raw').resolve()
    audio_cache_dir = str(Path('outputs/audio_cache').resolve())
    download_dir = str(Path('outputs/downloads').resolve())
    cmd = [
        sys.executable, '-X', 'utf8', str(script),
        video_path,
        '--output-dir', output_dir,
        '--raw-dir', str(raw_dir),
        '--audio-cache-dir', audio_cache_dir,
        '--download-dir', download_dir,
        '--whisper-model', model,
        '--whisper-device', device,
        '--whisper-compute-type', compute_type,
        '--language', language,
    ]
    if dry_run:
        cmd.append('--dry-run')

    env = _build_env()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=None, env=env)
    stdout_bytes, _ = proc.communicate()
    stdout = stdout_bytes.decode('utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError(stdout or f'exit code {proc.returncode}')
    return json.loads(stdout)
