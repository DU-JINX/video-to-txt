#!/usr/bin/env python3
"""视频批量转文本入口程序，支持 NAS 挂载目录 / 本地目录 / URL 列表三种输入源."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from video_to_txt.core.transcriber import transcribe
from video_to_txt.io.progress import is_done, load_progress, mark_done, mark_error
from video_to_txt.io.source_resolver import resolve_sources


def _detect_device() -> tuple[str, str]:
    """自动探测推理设备，返回 (device, compute_type)."""
    try:
        import torch
        if torch.cuda.is_available():
            return 'cuda', 'float16'
    except ImportError:
        pass
    return 'cpu', 'int8'


def _build_output_dir(base: Path, key: str) -> str:
    """根据任务 key 构建镜像输出目录."""
    p = Path(key)
    # url/绝对路径模式下，直接用文件父目录名+文件名组合
    if p.is_absolute() or key.startswith('http'):
        out = base / p.parent.name
    else:
        out = base / p.parent
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='视频批量转文本（支持 NAS / 本地 / URL 三种来源）')
    p.add_argument(
        '--source-mode', required=True,
        choices=['nas', 'local', 'url'],
        help='输入源类型: nas=NAS挂载目录  local=本地目录  url=URL列表文件',
    )
    p.add_argument('--input-dir', help='nas/local 模式：视频根目录')
    p.add_argument('--url-file', help='url 模式：每行一个视频 URL 的文本文件（# 开头为注释）')
    p.add_argument('--output-base', default='./outputs/final', help='本地输出根目录')
    p.add_argument('--whisper-model', default='small', help='Whisper 模型: tiny/base/small/medium/large-v3')
    p.add_argument('--whisper-device', default='auto', help='推理设备: auto/cpu/cuda')
    p.add_argument('--whisper-compute-type', default='auto', help='计算精度: auto/int8/float16')
    p.add_argument('--language', default='zh', help='识别语言，如 zh/en')
    p.add_argument('--dry-run', action='store_true', help='只扫描/解析来源，不执行转写')
    p.add_argument('--exclude', nargs='*', default=[], help='（目录模式）排除的目录名，可多个')
    p.add_argument('--include-dirs', nargs='*', default=None,
                   help='只处理这些直接父目录名下的文件，如: 主机位 固定机位')
    return p.parse_args()


def main() -> None:
    """批量转写主流程."""
    args = _parse_args()
    output_base = Path(args.output_base).resolve()

    device = args.whisper_device
    compute_type = args.whisper_compute_type
    if device == 'auto' or compute_type == 'auto':
        detected_device, detected_compute = _detect_device()
        if device == 'auto':
            device = detected_device
        if compute_type == 'auto':
            compute_type = detected_compute
    print(f'  推理设备: {device}  计算精度: {compute_type}')

    tasks = resolve_sources(
        source_mode=args.source_mode,
        input_dir=args.input_dir,
        url_file=args.url_file,
        exclude=args.exclude,
        include_dirs=args.include_dirs,
    )

    progress = load_progress()
    total = len(tasks)
    done_count = sum(1 for t in tasks if is_done(progress, t['key']))
    pending = total - done_count

    batch_start = time.time()
    print('=' * 60)
    print(f'  任务开始时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  输入源模式：  {args.source_mode}')
    print(f'  视频总数：    {total} 个')
    print(f'  已完成：      {done_count} 个')
    print(f'  待处理：      {pending} 个')
    print('=' * 60 + '\n')

    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks, 1):
        key = task['key']
        if is_done(progress, key):
            print(f'[{i}/{total}] 跳过（已完成）: {task["name"]}')
            continue

        out_dir = _build_output_dir(output_base, key)
        file_start = time.time()
        size_info = f'  ({task["size_mb"]} MB)' if task['size_mb'] is not None else ''
        print(f'[{i}/{total}] 开始处理: {task["name"]}{size_info}')
        print(f'  开始时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
        try:
            result = transcribe(
                task['source'], out_dir,
                model=args.whisper_model,
                device=device,
                compute_type=compute_type,
                language=args.language,
                dry_run=args.dry_run,
            )
            txt_path = result.get('final_txt_path')
            if not args.dry_run:
                mark_done(progress, key, result)
            success_count += 1
            elapsed = time.time() - file_start
            print(f'  结束时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'  耗时：    {elapsed:.1f} 秒')
            print(f'  输出至：  {txt_path or out_dir}\n')
        except Exception as e:
            mark_error(progress, key, str(e))
            fail_count += 1
            elapsed = time.time() - file_start
            print(f'  结束时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
            print(f'  耗时：    {elapsed:.1f} 秒')
            print(f'  失败：    {e}\n')

    total_elapsed = time.time() - batch_start
    print('=' * 60)
    print(f'  任务结束时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  总耗时：      {total_elapsed:.1f} 秒')
    print(f'  成功：        {success_count} 个')
    print(f'  失败：        {fail_count} 个')
    print('=' * 60)


if __name__ == '__main__':
    main()
