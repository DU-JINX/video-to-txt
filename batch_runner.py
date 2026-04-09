#!/usr/bin/env python3
"""NAS 视频批量转文本入口程序."""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from progress import is_done, load_progress, mark_done, mark_error
from scanner import scan_videos
from transcriber import transcribe

# NAS 默认根目录
NAS_ROOT = (
    r'\\192.168.3.3\内容资料\07PRO项目'
    r'\2024.12.09【宝藏S5000AI&内容项目】'
    r'\03视频语料库\00源素材-视频'
)


def build_output_dir(base: Path, rel_path: str) -> str:
    """根据相对路径构建镜像输出目录."""
    out = base / Path(rel_path).parent
    out.mkdir(parents=True, exist_ok=True)
    return str(out)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='NAS 视频批量转文本')
    p.add_argument('--nas-root', default=NAS_ROOT, help='NAS 视频根目录')
    p.add_argument('--output-base', default='./outputs/final', help='本地输出根目录')
    p.add_argument('--whisper-model', default='small', help='Whisper 模型: tiny/base/small/medium')
    p.add_argument('--whisper-device', default='cuda', help='推理设备: auto/cpu/cuda')
    p.add_argument('--whisper-compute-type', default='float16', help='计算精度: int8/float16')
    p.add_argument('--language', default='zh', help='识别语言')
    p.add_argument('--dry-run', action='store_true', help='只扫描不转写')
    p.add_argument('--exclude', nargs='*', default=[], help='排除的目录名，可多个')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    output_base = Path(args.output_base).resolve()
    progress = load_progress()
    files = scan_videos(args.nas_root, exclude=args.exclude)

    total = len(files)
    done_count = sum(1 for f in files if is_done(progress, f['rel_path']))
    pending = total - done_count

    batch_start = time.time()
    print('=' * 60)
    print(f'  任务开始时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  视频总数：    {total} 个')
    print(f'  已完成：      {done_count} 个')
    print(f'  待处理：      {pending} 个')
    print('=' * 60 + '\n')

    success_count = 0
    fail_count = 0

    for i, f in enumerate(files, 1):
        key = f['rel_path']
        if is_done(progress, key):
            print(f'[{i}/{total}] 跳过（已完成）: {f["name"]}')
            continue

        out_dir = build_output_dir(output_base, key)
        file_start = time.time()
        print(f'[{i}/{total}] 开始处理: {f["name"]}  ({f["size_mb"]} MB)')
        print(f'  开始时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
        try:
            result = transcribe(
                f['full_path'], out_dir,
                model=args.whisper_model,
                device=args.whisper_device,
                compute_type=args.whisper_compute_type,
                language=args.language,
                dry_run=args.dry_run,
            )
            txt_path = result.get('final_txt_path')
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
            print(f'  ✗ 失败：  {e}\n')

    total_elapsed = time.time() - batch_start
    print('=' * 60)
    print(f'  任务结束时间：{time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  总耗时：      {total_elapsed:.1f} 秒')
    print(f'  成功：        {success_count} 个')
    print(f'  失败：        {fail_count} 个')
    print('=' * 60)


if __name__ == '__main__':
    main()
