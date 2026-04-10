"""转写进度持久化管理."""
from __future__ import annotations

import json
from pathlib import Path

PROGRESS_FILE = Path('outputs/logs/progress.json')


def load_progress() -> dict:
    """加载进度记录，文件不存在则返回空字典."""
    if PROGRESS_FILE.exists():
        return json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
    return {}


def save_progress(data: dict) -> None:
    """持久化进度记录到 JSON 文件."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def mark_done(progress: dict, key: str, result: dict) -> None:
    """标记指定文件为已完成."""
    progress[key] = {'status': 'done', **result}
    save_progress(progress)


def mark_error(progress: dict, key: str, error: str) -> None:
    """标记指定文件为失败，记录错误信息."""
    progress[key] = {'status': 'error', 'error': error}
    save_progress(progress)


def is_done(progress: dict, key: str) -> bool:
    """判断指定文件是否已成功转写."""
    return progress.get(key, {}).get('status') == 'done'
