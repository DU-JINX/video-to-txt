"""FastAPI 请求与响应模型."""
from __future__ import annotations

from pydantic import BaseModel, Field


class TranscribeRequest(BaseModel):
    """转写请求体."""

    url: str = Field(..., description='视频 URL（OSS 直链或其他可访问地址）')
    title: str = Field('', description='视频标题，可选')
    language: str = Field('zh', description='音频语言，默认 zh')
    whisperModel: str = Field('small', description='Whisper 模型大小')


class TranscribeResponse(BaseModel):
    """转写响应体."""

    ok: bool
    title: str = ''
    text: str = ''
    error: str = ''


class NasTranscribeRequest(BaseModel):
    """NAS 转写请求体.

    三种模式：
    1. 单文件：nasPath 带视频扩展名（如 /volume1/videos/a.mp4）
    2. 目录扫描：nasPath 为目录，扫描所有视频
    3. 目录排除：目录模式 + exclude 指定跳过的子路径
    """

    nasPath: str = Field(..., description='NAS 文件或目录路径')
    exclude: list[str] = Field(default_factory=list, description='扫描时排除的子路径列表')
    language: str = Field('zh', description='音频语言，默认 zh')
    whisperModel: str = Field('small', description='Whisper 模型大小')

