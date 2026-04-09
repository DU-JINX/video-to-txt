from __future__ import annotations

from pathlib import Path


def to_simplified(text: str) -> str:
    """繁体中文转简体中文."""
    import opencc
    converter = opencc.OpenCC('t2s')
    return converter.convert(text)


def convert_file(path: str) -> None:
    """将指定 txt 文件繁体转简体, 原地覆盖."""
    p = Path(path)
    original = p.read_text(encoding='utf-8')
    simplified = to_simplified(original)
    p.write_text(simplified, encoding='utf-8')
