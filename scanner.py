from __future__ import annotations

from pathlib import Path

# 支持的媒体扩展名（小写匹配）
VIDEO_EXTS = {'.mp4', '.mp3', '.mov', '.avi', '.mkv', '.flv', '.wmv'}


def scan_videos(root: str, exclude: list[str] | None = None) -> list[dict]:
    """递归扫描目录, 返回所有媒体文件信息列表.

    Args:
        root: 根目录路径
        exclude: 要排除的目录名列表（精确匹配任意层级目录名）
    """
    root_path = Path(root)
    exclude_set = set(exclude or [])
    files = []
    for f in root_path.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        if exclude_set and any(p.name in exclude_set for p in f.parents):
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
