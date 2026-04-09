#!/usr/bin/env python3
"""轻量转录脚本: 每个音频块独立进程, CUDA 上下文彻底隔离."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio")
    parser.add_argument("--model", default="small")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--language", default=None)
    parser.add_argument("--label", default="转录")
    args = parser.parse_args()

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print(json.dumps({"ok": False, "error": "faster-whisper not installed"}))
        sys.stdout.flush()
        os._exit(1)

    model = WhisperModel(
        args.model, device=args.device, compute_type=args.compute_type,
    )
    seg_iter, info = model.transcribe(
        args.audio, language=args.language,
        beam_size=1, vad_filter=True,
    )
    total = getattr(info, "duration", None)

    try:
        from tqdm import tqdm
        bar = tqdm(
            total=int(total) if total else None,
            unit="s", unit_scale=True,
            desc=args.label, file=sys.stderr,
            bar_format="{l_bar}{bar}| {n:.0f}/{total:.0f}s [{elapsed}<{remaining}]",
        )
    except ImportError:
        bar = None

    segments = []
    for seg in seg_iter:
        segments.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": seg.text.strip(),
        })
        if bar is not None:
            bar.n = int(seg.end)
            bar.refresh()

    if bar is not None:
        bar.close()

    result = {
        "ok": True,
        "segments": segments,
        "language": getattr(info, "language", None),
        "duration": getattr(info, "duration", None),
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.stdout.flush()
    # 跳过 CUDA cleanup, 避免析构崩溃
    os._exit(0)


if __name__ == "__main__":
    main()
