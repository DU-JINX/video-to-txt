#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

USER_AGENT = "video-to-text-standalone/1.0"
DEFAULT_HF_ENDPOINT = "https://hf-mirror.com"


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_name(name: str) -> str:
    return re.sub(r"[\\/:*?\"<>|\r\n]+", "_", name).strip().strip(".") or "video-transcript"


def add_txt_suffix(name: str) -> str:
    return name if name.lower().endswith(".txt") else f"{name}.txt"


def strip_final_extension(name: str) -> str:
    return name.rsplit(".", 1)[0] if "." in name else name


def load_faster_whisper():
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Missing Python package: faster-whisper. Install it with: python3 -m pip install -r requirements.txt"
        ) from exc
    return WhisperModel


def check_dependencies() -> dict:
    issues: list[str] = []
    hints: list[str] = []

    if sys.version_info < (3, 10):
        issues.append(f"python3 version too old: {sys.version.split()[0]}")
        hints.append("Install Python 3.10+.")

    if not command_exists("ffprobe"):
        issues.append("Missing command: ffprobe")
        hints.append("Install ffmpeg first. Ubuntu/Debian: sudo apt-get update && sudo apt-get install -y ffmpeg")

    if not module_exists("faster_whisper"):
        issues.append("Missing Python package: faster-whisper")
        hints.append("Run: python3 -m pip install -r requirements.txt")

    return {
        "ok": not issues,
        "python_version": sys.version.split()[0],
        "checks": {
            "ffprobe": command_exists("ffprobe"),
            "faster_whisper": module_exists("faster_whisper"),
        },
        "issues": issues,
        "install_hints": hints,
    }


def format_subprocess_error(exc: subprocess.CalledProcessError) -> str:
    stdout = (exc.stdout or "").strip()
    stderr = (exc.stderr or "").strip()
    detail = stderr or stdout or str(exc)
    return f"Command failed: {' '.join(exc.cmd)}\n{detail}"


def run_json(cmd: list[str]) -> dict:
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(format_subprocess_error(exc)) from exc
    return json.loads(proc.stdout)


def guess_name_from_headers(headers, url: str, title: str | None = None) -> str:
    content_disposition = headers.get("Content-Disposition", "")
    filename = None
    match = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition, re.I)
    if match:
        filename = unquote(match.group(1))
    if not filename:
        match = re.search(r'filename="?([^";]+)"?', content_disposition, re.I)
        if match:
            filename = match.group(1)
    if not filename:
        path_name = Path(unquote(urlparse(url).path)).name
        if path_name:
            filename = path_name
    if not filename and title:
        filename = title
    if not filename:
        filename = "video"

    filename = safe_name(filename)
    if "." not in filename:
        content_type = (headers.get("Content-Type") or "").split(";")[0].strip().lower()
        ext = mimetypes.guess_extension(content_type) or ""
        filename += ext
    return filename


def materialize_source(source: str, download_dir: Path, title: str | None, timeout: int) -> dict:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        ensure_dir(download_dir)
        request = Request(source, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as resp:
            filename = guess_name_from_headers(resp.headers, source, title)
            out_path = download_dir / filename
            with out_path.open("wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
            return {
                "path": str(out_path.resolve()),
                "downloaded": True,
                "filename": filename,
                "final_url": resp.geturl(),
                "status_code": getattr(resp, "status", None),
                "content_type": (resp.headers.get("Content-Type") or "application/octet-stream").split(";")[0].strip(),
                "size": out_path.stat().st_size,
            }

    local_path = Path(parsed.path if parsed.scheme == "file" else source).expanduser().resolve()
    if not local_path.exists() or not local_path.is_file():
        raise FileNotFoundError(f"Source file not found: {local_path}")
    return {
        "path": str(local_path),
        "downloaded": False,
        "filename": local_path.name,
        "final_url": None,
        "status_code": None,
        "content_type": mimetypes.guess_type(local_path.name)[0] or "application/octet-stream",
        "size": local_path.stat().st_size,
    }


def ffprobe_json(input_path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe not found. Install ffmpeg first.")
    return run_json([
        ffprobe,
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(input_path),
    ])


def summarize_probe(probe: dict, input_path: Path) -> dict:
    fmt = probe.get("format", {})
    video = None
    audio = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video" and video is None:
            video = stream
        elif stream.get("codec_type") == "audio" and audio is None:
            audio = stream

    fps = None
    if video:
        raw_rate = video.get("avg_frame_rate") or video.get("r_frame_rate")
        if raw_rate and raw_rate != "0/0":
            num, den = raw_rate.split("/")
            if den != "0":
                fps = round(float(num) / float(den), 3)

    return {
        "input": str(input_path),
        "format_name": fmt.get("format_name"),
        "duration_seconds": float(fmt["duration"]) if fmt.get("duration") else None,
        "size_bytes": int(fmt["size"]) if fmt.get("size") else None,
        "bit_rate": int(fmt["bit_rate"]) if fmt.get("bit_rate") else None,
        "video": {
            "codec": video.get("codec_name") if video else None,
            "width": video.get("width") if video else None,
            "height": video.get("height") if video else None,
            "fps": fps,
            "pix_fmt": video.get("pix_fmt") if video else None,
        },
        "audio": {
            "codec": audio.get("codec_name") if audio else None,
            "channels": audio.get("channels") if audio else None,
            "sample_rate": int(audio["sample_rate"]) if audio and audio.get("sample_rate") else None,
        },
        "streams": len(probe.get("streams", [])),
    }


def derive_output_filename(source: str, local_path: Path, output_name: str | None, title: str | None) -> str:
    if output_name:
        return add_txt_suffix(safe_name(output_name))

    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        basename = Path(unquote(parsed.path)).name
        if basename and basename not in {".", ".."}:
            return add_txt_suffix(safe_name(strip_final_extension(basename)))

    if local_path.stem:
        return add_txt_suffix(safe_name(local_path.stem))
    if title:
        return add_txt_suffix(safe_name(title))
    return "video-transcript.txt"


def transcribe_file(
    input_path: Path,
    *,
    model_name: str,
    device: str,
    compute_type: str,
    language: str | None,
    hf_endpoint: str,
    cache_dir: Path,
) -> tuple[list[dict], dict]:
    WhisperModel = load_faster_whisper()
    os.environ.setdefault("HF_ENDPOINT", hf_endpoint)
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cache_dir))
    ensure_dir(cache_dir)

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments_iter, info = model.transcribe(str(input_path), language=language)
    segments: list[dict] = []
    for segment in segments_iter:
        segments.append(
            {
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
            }
        )
    info_dict = {
        "language": getattr(info, "language", None),
        "language_probability": getattr(info, "language_probability", None),
        "duration": getattr(info, "duration", None),
    }
    return segments, info_dict


def write_raw_txt(path: Path, segments: list[dict]) -> None:
    ensure_dir(path.parent)
    path.write_text("\n".join(seg["text"].strip() for seg in segments).strip() + "\n", encoding="utf-8")


def build_final_body(*, title: str, source: str, local_path: Path, inspect: dict, raw_text: str, transcript_info: dict) -> str:
    generated_at = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S %Z")
    duration = inspect.get("duration_seconds")
    width = (inspect.get("video") or {}).get("width")
    height = (inspect.get("video") or {}).get("height")
    fps = (inspect.get("video") or {}).get("fps")
    audio_codec = (inspect.get("audio") or {}).get("codec")
    video_codec = (inspect.get("video") or {}).get("codec")

    parts = [
        f"标题：{title}",
        "来源类型：视频",
        f"来源：{source}",
        f"本地文件：{local_path}",
        f"生成时间：{generated_at}",
    ]
    if transcript_info.get("language"):
        parts.append(f"识别语言：{transcript_info['language']}")
    if duration is not None:
        parts.append(f"时长秒数：{duration}")
    if video_codec:
        parts.append(f"视频编码：{video_codec}")
    if width and height:
        parts.append(f"分辨率：{width}x{height}")
    if fps is not None:
        parts.append(f"帧率：{fps}")
    if audio_codec:
        parts.append(f"音频编码：{audio_codec}")

    return "\n".join(parts) + "\n\n以下为根据原始转写生成的文本初稿：\n\n" + raw_text.strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Standalone video-to-text script for new environments.")
    parser.add_argument("source", nargs="?", help="Video URL (http/https) or local file path")
    parser.add_argument("--title", help="Optional title override written into the final txt")
    parser.add_argument("--output-dir", default="./outputs/final", help="Directory for final txt outputs")
    parser.add_argument("--download-dir", default="./outputs/downloads", help="Directory for downloaded remote videos")
    parser.add_argument("--raw-dir", default="./outputs/raw", help="Directory for raw transcript txt")
    parser.add_argument("--cache-dir", default="./.cache/huggingface", help="Model/cache directory")
    parser.add_argument("--output-name", help="Optional final txt filename or basename; .txt is appended automatically if missing")
    parser.add_argument("--timeout", type=int, default=300, help="HTTP timeout in seconds for remote video download")
    parser.add_argument("--whisper-model", default="base", help="Whisper model size, e.g. tiny/base/small/medium/large-v3")
    parser.add_argument("--whisper-device", default="auto", help="Inference device: auto/cpu/cuda")
    parser.add_argument("--whisper-compute-type", default="int8", help="faster-whisper compute type")
    parser.add_argument("--language", help="Optional language code, e.g. zh or en")
    parser.add_argument("--hf-endpoint", default=os.environ.get("HF_ENDPOINT", DEFAULT_HF_ENDPOINT), help="Hugging Face endpoint or mirror")
    parser.add_argument("--dry-run", action="store_true", help="Only materialize source + inspect media; do not transcribe or write final txt")
    parser.add_argument("--check-deps", action="store_true", help="Check runtime dependencies and print a machine-readable report")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    dep_report = check_dependencies()
    if args.check_deps:
        print(json.dumps(dep_report, ensure_ascii=False, indent=2))
        return 0 if dep_report["ok"] else 1

    if not args.source:
        print(json.dumps({
            "ok": False,
            "error": "Missing required argument: source",
            "hint": "Pass a video URL/local file path, or run with --check-deps first.",
        }, ensure_ascii=False, indent=2))
        return 2

    if not dep_report["ok"]:
        print(json.dumps({
            "ok": False,
            "error": "Dependency check failed",
            "dependency_report": dep_report,
        }, ensure_ascii=False, indent=2))
        return 1

    try:
        output_dir = Path(args.output_dir).expanduser().resolve()
        download_dir = Path(args.download_dir).expanduser().resolve()
        raw_dir = Path(args.raw_dir).expanduser().resolve()
        cache_dir = Path(args.cache_dir).expanduser().resolve()
        ensure_dir(output_dir)
        ensure_dir(raw_dir)
        ensure_dir(download_dir)
        ensure_dir(cache_dir)

        source_meta = materialize_source(args.source, download_dir, args.title, args.timeout)
        local_path = Path(source_meta["path"]).resolve()

        try:
            inspect_probe = ffprobe_json(local_path)
            inspect = summarize_probe(inspect_probe, local_path)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to inspect media. The file may be incomplete/corrupted or not a valid video container.\n{exc}"
            ) from exc

        output_filename = derive_output_filename(args.source, local_path, args.output_name, args.title)
        title = args.title or strip_final_extension(output_filename)
        final_txt_path = output_dir / output_filename
        raw_txt_path = raw_dir / add_txt_suffix(safe_name(strip_final_extension(output_filename) + ".raw"))

        result = {
            "ok": True,
            "source": args.source,
            "title": title,
            "local_file": source_meta,
            "inspect": inspect,
            "dry_run": args.dry_run,
            "planned_raw_txt_path": str(raw_txt_path),
            "planned_final_txt_path": str(final_txt_path),
        }

        if args.dry_run:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0

        try:
            segments, transcript_info = transcribe_file(
                local_path,
                model_name=args.whisper_model,
                device=args.whisper_device,
                compute_type=args.whisper_compute_type,
                language=args.language,
                hf_endpoint=args.hf_endpoint,
                cache_dir=cache_dir,
            )
        except Exception as exc:
            raise RuntimeError(f"Failed to transcribe media.\n{exc}") from exc

        write_raw_txt(raw_txt_path, segments)
        raw_text = raw_txt_path.read_text(encoding="utf-8")
        # 繁体转简体
        try:
            import opencc
            raw_text = opencc.OpenCC('t2s').convert(raw_text)
        except ImportError:
            pass
        final_body = build_final_body(
            title=title,
            source=args.source,
            local_path=local_path,
            inspect=inspect,
            raw_text=raw_text,
            transcript_info=transcript_info,
        )
        final_txt_path.write_text(final_body, encoding="utf-8")

        result.update({
            "raw_transcript_path": str(raw_txt_path),
            "final_txt_path": str(final_txt_path),
            "transcript_info": transcript_info,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({
            "ok": False,
            "error": str(exc),
        }, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
