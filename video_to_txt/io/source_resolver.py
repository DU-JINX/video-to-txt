"""多模式输入源解析：nas / local / url 三种来源统一转换为任务列表."""
from __future__ import annotations

from pathlib import Path

from video_to_txt.io.scanner import scan_videos


def resolve_sources(
    source_mode: str,
    input_dir: str | None,
    url_file: str | None,
    exclude: list[str],
    include_dirs: list[str] | None = None,
) -> list[dict]:
    """统一解析输入源，返回任务列表.

    Args:
        source_mode: 来源模式，可选 nas / local / url.
        input_dir: nas/local 模式下的视频根目录路径.
        url_file: url 模式下的 URL 列表文件路径（每行一个，# 开头为注释）.
        exclude: 要排除的目录名列表.

    Returns:
        任务字典列表，每项含 source/key/name/size_mb/is_url.

    Raises:
        ValueError: source_mode 不合法或必要参数缺失时抛出.
    """
    if source_mode in ('nas', 'local'):
        if not input_dir:
            raise ValueError(f'--source-mode {source_mode} 需要同时指定 --input-dir')
        files = scan_videos(input_dir, exclude=exclude, include_dirs=include_dirs)
        return [
            {
                'source': f['full_path'],
                'key': f['rel_path'],
                'name': f['name'],
                'size_mb': f['size_mb'],
                'is_url': False,
            }
            for f in files
        ]

    if source_mode == 'url':
        if not url_file:
            raise ValueError('--source-mode url 需要同时指定 --url-file')
        lines = Path(url_file).read_text(encoding='utf-8').splitlines()
        tasks = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            name = line.rsplit('/', 1)[-1] or line
            tasks.append({
                'source': line,
                'key': line,
                'name': name,
                'size_mb': None,
                'is_url': True,
            })
        return tasks

    raise ValueError(f'未知 source_mode: {source_mode!r}，可选值: nas / local / url')
