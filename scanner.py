from __future__ import annotations

from pathlib import Path

# 支持的媒体扩展名（小写匹配）
VIDEO_EXTS = {'.mp4', '.mp3', '.mov', '.avi', '.mkv', '.flv', '.wmv'}


def scan_videos(root: str) -> list[dict]:
    """递归扫描目录, 返回所有媒体文件信息列表."""
    root_path = Path(root)
    files = []
    for f in root_path.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        rel = f.relative_to(root_path)
        files.append({
            'full_path': str(f),
            'rel_path': str(rel),
            'name': f.name,
            'stem': f.stem,
            'size_mb': round(f.stat().st_size / 1024 / 1024, 1),
        })
    return files
