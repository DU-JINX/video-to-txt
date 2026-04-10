"""繁简体文本转换工具."""
from __future__ import annotations

from pathlib import Path


def to_simplified(text: str) -> str:
    """将繁体中文文本转换为简体中文.

    Args:
        text: 繁体中文文本.

    Returns:
        简体中文文本.
    """
    import opencc
    converter = opencc.OpenCC('t2s')
    return converter.convert(text)


def convert_file(path: str) -> None:
    """将指定 txt 文件繁体转简体，原地覆盖.

    Args:
        path: 目标文件路径.
    """
    p = Path(path)
    original = p.read_text(encoding='utf-8')
    simplified = to_simplified(original)
    p.write_text(simplified, encoding='utf-8')
