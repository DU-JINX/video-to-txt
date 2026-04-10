"""FastAPI 路由定义."""
from __future__ import annotations

import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from api.models import NasTranscribeRequest, TranscribeRequest
from video_to_txt.core.transcriber import transcribe
from video_to_txt.io.nas_downloader import NasConfig, download_file, is_video_file, list_video_files

OUTPUT_DIR = Path('outputs/result').resolve()


@asynccontextmanager
async def lifespan(app: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title='video-to-txt 转写服务', version='1.0.0', lifespan=lifespan)


@app.post('/api/transcribe')
def do_transcribe(req: TranscribeRequest):
    """接收视频 URL，调用转写核心模块，以 txt 文件流返回."""
    try:
        result = transcribe(
            req.url,
            str(OUTPUT_DIR),
            model=req.whisperModel,
            language=req.language,
        )
        final_txt = Path(result['final_txt_path'])
        title = req.title or result.get('title', final_txt.stem)

        cleanup_targets: list[str] = []
        raw_path = result.get('raw_transcript_path')
        if raw_path:
            cleanup_targets.append(raw_path)
        local_file = result.get('local_file', {})
        if local_file.get('downloaded') and local_file.get('path'):
            cleanup_targets.append(local_file['path'])

        return FileResponse(
            path=str(final_txt),
            media_type='text/plain; charset=utf-8',
            filename=f'{title}.txt',
            background=BackgroundTask(_cleanup, final_txt, cleanup_targets),
        )
    except Exception as exc:
        return JSONResponse(status_code=500, content={'ok': False, 'error': str(exc)})


@app.post('/api/nas/transcribe')
def do_nas_transcribe(req: NasTranscribeRequest):
    """NAS 视频转写接口.

    支持三种模式：
    - 单文件：nasPath 带视频扩展名
    - 目录扫描：nasPath 为目录
    - 目录排除：目录模式 + exclude 子路径
    """
    try:
        config = NasConfig.from_env()
        if is_video_file(req.nasPath):
            return _nas_single_file(config, req)
        return _nas_directory(config, req)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={'ok': False, 'error': str(exc)})
    except Exception as exc:
        return JSONResponse(status_code=500, content={'ok': False, 'error': str(exc)})


@app.get('/health')
def health():
    """健康检查接口."""
    return {'status': 'ok'}


def _nas_single_file(config: NasConfig, req: NasTranscribeRequest) -> FileResponse:
    """单文件模式：从 NAS 下载 → 转写 → 返回文件流.

    Args:
        config: NAS 连接配置.
        req: 请求体.

    Returns:
        FileResponse，响应后自动清理中间文件.
    """
    filename = PurePosixPath(req.nasPath).name
    title = PurePosixPath(req.nasPath).stem
    local_dir = tempfile.mkdtemp(prefix='nas_')
    local_video = os.path.join(local_dir, filename)
    download_file(config, req.nasPath, local_video)

    result = transcribe(local_video, str(OUTPUT_DIR), model=req.whisperModel, language=req.language)
    final_txt = Path(result['final_txt_path'])

    cleanup_targets: list[str] = [local_video, local_dir]
    raw_path = result.get('raw_transcript_path')
    if raw_path:
        cleanup_targets.append(raw_path)

    return FileResponse(
        path=str(final_txt),
        media_type='text/plain; charset=utf-8',
        filename=f'{title}.txt',
        background=BackgroundTask(_cleanup_nas, final_txt, cleanup_targets),
    )


def _nas_directory(config: NasConfig, req: NasTranscribeRequest) -> JSONResponse:
    """目录扫描模式：批量获取视频 → 逐个转写 → 返回 JSON 结果.

    Args:
        config: NAS 连接配置.
        req: 请求体.

    Returns:
        JSONResponse，包含每个文件的转写结果和文本内容.
    """
    video_files = list_video_files(config, req.nasPath, req.exclude)
    if not video_files:
        return JSONResponse(content={'ok': True, 'total': 0, 'succeeded': 0, 'failed': 0, 'results': []})

    results = []
    succeeded = 0
    failed = 0

    for remote_path in video_files:
        filename = PurePosixPath(remote_path).name
        local_dir = tempfile.mkdtemp(prefix='nas_')
        local_video = os.path.join(local_dir, filename)
        try:
            download_file(config, remote_path, local_video)
            result = transcribe(local_video, str(OUTPUT_DIR), model=req.whisperModel, language=req.language)
            final_txt = Path(result['final_txt_path'])
            text = final_txt.read_text(encoding='utf-8')

            cleanup_targets = [local_video, local_dir]
            raw_path = result.get('raw_transcript_path')
            if raw_path:
                cleanup_targets.append(raw_path)
            _cleanup_nas(final_txt, cleanup_targets)

            results.append({'filename': filename, 'ok': True, 'textLength': len(text), 'text': text})
            succeeded += 1
        except Exception as exc:
            _cleanup_nas(None, [local_video, local_dir])
            results.append({'filename': filename, 'ok': False, 'error': str(exc)})
            failed += 1

    return JSONResponse(content={
        'ok': True,
        'total': len(video_files),
        'succeeded': succeeded,
        'failed': failed,
        'results': results,
    })


def _cleanup(final_path: Path, extra: list[str]) -> None:
    """响应发送完成后清理 raw 文件和已下载的视频文件.

    Args:
        final_path: 转写结果 txt 文件路径.
        extra: 额外需要删除的路径列表.
    """
    for p in [str(final_path)] + extra:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass


def _cleanup_nas(final_path: Path | None, extra: list[str]) -> None:
    """清理 NAS 转写产生的本地临时文件和目录.

    Args:
        final_path: 转写结果 txt 文件，为 None 时跳过.
        extra: 临时视频文件和目录路径列表.
    """
    if final_path:
        try:
            final_path.unlink(missing_ok=True)
        except Exception:
            pass
    for p in extra:
        try:
            target = Path(p)
            if target.is_dir():
                import shutil
                shutil.rmtree(p, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        except Exception:
            pass
