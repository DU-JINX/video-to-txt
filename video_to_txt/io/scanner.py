"""目录媒体文件递归扫描."""
from __future__ import annotations

from pathlib import Path

VIDEO_EXTS = {'.mp4', '.mp3', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.mxf'}


def scan_videos(
    root: str,
    exclude: list[str] | None = None,
    include_dirs: list[str] | None = None,
) -> list[dict]:
    """递归扫描目录，返回所有媒体文件信息列表.

    Args:
        root: 根目录路径.
        exclude: 要排除的目录名列表（精确匹配任意层级目录名）.
        include_dirs: 若指定，文件必须直接在这些目录名之下（如主机位/固定机位）.

    Returns:
        媒体文件信息字典列表，每项含 full_path/rel_path/name/stem/size_mb.
    """
    root_path = Path(root)
    exclude_set = set(exclude or [])
    include_set = set(include_dirs or [])
    files = []
    for f in root_path.rglob('*'):
        if not f.is_file():
            continue
        if f.suffix.lower() not in VIDEO_EXTS:
            continue
        if exclude_set and any(p.name in exclude_set for p in f.parents):
            continue
        # 若指定了 include_dirs，文件直接父目录名必须在其中
        if include_set and f.parent.name not in include_set:
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
