"""Assemble Seedance scene clips into a delivery-ready preview package."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from gemeiqi.repository import dump_json

DEFAULT_FINAL_SCENES = [1, 2, 3, 5, 8, 9, 10, 16]
DEFAULT_SCENE_SUBTITLES = {
    1: "\u4e0a\u811a\u5148\u770b\u6bd4\u4f8b",
    2: "\u53cc\u5e26\u739b\u4e3d\u73cd\u66f4\u663e\u811a\u578b",
    3: "\u978b\u5934\u8f6e\u5ed3\u5f88\u79c0\u6c14",
    5: "\u4f4e\u8ddf\u8d70\u8def\u66f4\u8f7b\u677e",
    8: "\u9ed1\u8272\u901a\u52e4\u5f88\u597d\u642d",
    9: "\u88d9\u88c5\u88e4\u88c5\u90fd\u80fd\u914d",
    10: "\u8fd1\u770b\u76ae\u9762\u6709\u5149\u6cfd",
    16: "\u65e5\u5e38\u51fa\u95e8\u4e00\u53cc\u591f",
}
DEFAULT_SCENE_VOICEOVERS = {
    1: "\u8fd9\u53cc\u5148\u770b\u4e0a\u811a\u6bd4\u4f8b\uff0c\u771f\u7684\u5f88\u987a\u773c\u3002",
    2: "\u53cc\u5e26\u739b\u4e3d\u73cd\u7684\u811a\u578b\u4fee\u9970\u611f\uff0c\u4e0a\u811a\u5c31\u80fd\u770b\u51fa\u6765\u3002",
    3: "\u978b\u5934\u7ebf\u6761\u79c0\u6c14\uff0c\u8fd1\u770b\u4e5f\u4e0d\u4f1a\u7b28\u91cd\u3002",
    5: "\u4f4e\u8ddf\u8d70\u8def\u66f4\u8f7b\u677e\uff0c\u65e5\u5e38\u901a\u52e4\u4e0d\u7d2f\u811a\u3002",
    8: "\u9ed1\u8272\u771f\u7684\u5f88\u597d\u642d\uff0c\u901a\u52e4\u548c\u65e5\u5e38\u90fd\u80fd\u7a7f\u3002",
    9: "\u88d9\u88c5\u88e4\u88c5\u90fd\u53ef\u4ee5\uff0c\u7a7f\u642d\u8303\u56f4\u5f88\u5e7f\u3002",
    10: "\u8fd1\u770b\u76ae\u9762\u6709\u5149\u6cfd\uff0c\u8d28\u611f\u4e0d\u662f\u90a3\u79cd\u5047\u4eae\u611f\u3002",
    16: "\u65e5\u5e38\u51fa\u95e8\u5907\u8fd9\u4e00\u53cc\uff0c\u771f\u7684\u5c31\u591f\u4e86\u3002",
}


def assemble_seedance_preview(
    download_dir: Path,
    output_file: Path | None = None,
    scene_indexes: list[int] | None = None,
    skip_scene_indexes: list[int] | None = None,
    seconds_per_scene: float = 1.45,
    start_offset_seconds: float = 0.2,
    fps: float = 24.0,
    subtitle_map: dict[int, str] | None = None,
    voiceover_map: dict[int, str] | None = None,
    scene_metadata: dict[int, dict[str, Any]] | None = None,
    draw_subtitles: bool = True,
    selection_enabled: bool = True,
    selection_step_seconds: float = 0.15,
    synthesize_narration: bool = False,
) -> dict[str, Any]:
    """Create a fast-cut preview plus delivery sidecar files."""

    if seconds_per_scene <= 0:
        raise ValueError("seconds_per_scene must be positive")
    if fps <= 0:
        raise ValueError("fps must be positive")
    if selection_step_seconds <= 0:
        raise ValueError("selection_step_seconds must be positive")

    scene_indexes = scene_indexes or DEFAULT_FINAL_SCENES
    skip = set(skip_scene_indexes or [])
    subtitle_map = subtitle_map or DEFAULT_SCENE_SUBTITLES
    voiceover_map = voiceover_map or DEFAULT_SCENE_VOICEOVERS
    scene_metadata = scene_metadata or {}
    processed_dir = download_dir / "processed"
    selected_scenes = [scene for scene in scene_indexes if scene not in skip]
    clips = [_scene_clip_path(processed_dir, scene_index) for scene_index in selected_scenes]
    missing = [str(path) for path in clips if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing processed Seedance clips: {missing}")

    probe = _probe_video(clips[0])
    width = probe["width"]
    height = probe["height"]
    output_file = output_file or download_dir / "seedance_final_preview.mp4"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    writer = cv2.VideoWriter(
        str(output_file),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot write preview video: {output_file}")

    timeline = []
    target_frames = max(1, int(round(seconds_per_scene * fps)))
    total_frames = 0
    selection_reviews = []
    try:
        for scene_index, clip_path in zip(selected_scenes, clips):
            selection = _select_clip_window(
                clip_path=clip_path,
                target_frames=target_frames,
                min_start_seconds=start_offset_seconds,
                step_seconds=selection_step_seconds,
                enabled=selection_enabled,
            )
            written = _write_clip_slice(
                writer=writer,
                clip_path=clip_path,
                subtitle=subtitle_map.get(scene_index, ""),
                draw_subtitles=draw_subtitles,
                output_size=(width, height),
                target_frames=target_frames,
                start_offset_seconds=selection["selected_start_seconds"],
            )
            total_frames += written
            metadata = scene_metadata.get(scene_index, {})
            entry = {
                "scene_index": scene_index,
                "clip_path": str(clip_path),
                "subtitle": subtitle_map.get(scene_index, ""),
                "voiceover": voiceover_map.get(scene_index, ""),
                "source_segment_index": metadata.get("source_segment_index"),
                "source_role": metadata.get("source_role", ""),
                "source_ocr_texts": metadata.get("source_ocr_texts", []),
                "selected_start_seconds": selection["selected_start_seconds"],
                "requested_start_seconds": start_offset_seconds,
                "selection_score": selection["selection_score"],
                "seconds": round(written / fps, 3),
                "frames": written,
            }
            timeline.append(entry)
            selection_reviews.append(
                {
                    "scene_index": scene_index,
                    "clip_path": str(clip_path),
                    "selection_enabled": selection_enabled,
                    "selected_start_seconds": selection["selected_start_seconds"],
                    "selection_score": selection["selection_score"],
                    "candidates": selection["candidates"],
                }
            )
    finally:
        writer.release()

    base_path = output_file.with_suffix("")
    subtitles_file = base_path.with_suffix(".srt")
    voiceover_script_file = base_path.with_name(f"{base_path.name}_voiceover.txt")
    delivery_notes_file = base_path.with_name(f"{base_path.name}_delivery.md")
    selection_review_file = base_path.with_name(f"{base_path.name}_selection.json")
    _write_srt(subtitles_file, timeline)
    _write_voiceover_script(voiceover_script_file, timeline)
    _write_delivery_notes(delivery_notes_file, timeline, output_file)
    dump_json(selection_review_file, {"scenes": selection_reviews})

    narration_wav = None
    narration_status = "not_requested"
    narration_debug_file = ""
    if synthesize_narration:
        narration_wav = base_path.with_name(f"{base_path.name}_voiceover.wav")
        narration_status = _synthesize_voiceover_wav(narration_wav, timeline)
        narration_log = narration_wav.with_suffix(".tts.log")
        if narration_log.exists():
            narration_debug_file = str(narration_log)
        if narration_status != "succeeded":
            narration_wav = None

    manifest = {
        "download_dir": str(download_dir),
        "output_video": str(output_file),
        "scene_indexes": selected_scenes,
        "skipped_scene_indexes": sorted(skip),
        "seconds_per_scene": seconds_per_scene,
        "fps": fps,
        "width": width,
        "height": height,
        "total_frames": total_frames,
        "duration_seconds": round(total_frames / fps, 3),
        "draw_subtitles": draw_subtitles,
        "selection_enabled": selection_enabled,
        "selection_step_seconds": selection_step_seconds,
        "subtitles_file": str(subtitles_file),
        "voiceover_script_file": str(voiceover_script_file),
        "delivery_notes_file": str(delivery_notes_file),
        "selection_review_file": str(selection_review_file),
        "narration_wav": str(narration_wav) if narration_wav else "",
        "narration_status": narration_status,
        "narration_debug_file": narration_debug_file,
        "audio_mux_ready": False,
        "timeline": timeline,
    }
    dump_json(output_file.with_suffix(".json"), manifest)
    return manifest


def build_scene_text_maps(
    plan: dict[str, Any] | None = None,
    script_output: dict[str, Any] | None = None,
    analysis: dict[str, Any] | None = None,
    scene_indexes: list[int] | None = None,
) -> tuple[dict[int, str], dict[int, str], dict[int, dict[str, Any]]]:
    """Build subtitle, voiceover, and metadata maps from plan plus analysis."""

    scene_indexes = scene_indexes or []
    segments = {int(item.get("scene_index")): item for item in (plan or {}).get("segments", [])}
    script_scenes = {int(item.get("index")): item for item in (script_output or {}).get("scenes", [])}
    analysis_segments = {int(item.get("index")): item for item in (analysis or {}).get("segments", [])}

    subtitle_map: dict[int, str] = {}
    voiceover_map: dict[int, str] = {}
    metadata: dict[int, dict[str, Any]] = {}
    for scene_index in scene_indexes:
        segment = segments.get(scene_index, {})
        script_scene = script_scenes.get(scene_index, {})
        subtitle = _choose_text(
            script_scene.get("subtitle_suggestion"),
            segment.get("subtitle_suggestion"),
            DEFAULT_SCENE_SUBTITLES.get(scene_index, ""),
        )
        voiceover = _choose_text(
            script_scene.get("narration_suggestion"),
            segment.get("narration_suggestion"),
            DEFAULT_SCENE_VOICEOVERS.get(scene_index, ""),
            subtitle,
        )
        source_segment_index = _coerce_int(
            script_scene.get("source_segment_index"),
            segment.get("source_segment_index"),
            scene_index,
        )
        source_ocr_texts: list[str] = []
        if isinstance(source_segment_index, int):
            source_segment = analysis_segments.get(source_segment_index, {})
            source_ocr_texts = _normalize_text_list(source_segment.get("ocr_texts", []))
        subtitle_map[scene_index] = subtitle
        voiceover_map[scene_index] = voiceover
        metadata[scene_index] = {
            "source_segment_index": source_segment_index,
            "source_ocr_texts": source_ocr_texts,
            "source_role": _choose_text(
                script_scene.get("role"),
                segment.get("role"),
                segment.get("role_guess"),
            ),
        }
    return subtitle_map, voiceover_map, metadata


def _scene_clip_path(processed_dir: Path, scene_index: int) -> Path:
    return processed_dir / f"scene_{scene_index:04d}_trimmed.mp4"


def _select_clip_window(
    clip_path: Path,
    target_frames: int,
    min_start_seconds: float,
    step_seconds: float,
    enabled: bool,
) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open Seedance clip: {clip_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    start_frame = max(0, int(round(min_start_seconds * source_fps)))
    max_start_frame = max(start_frame, frame_count - target_frames)
    step_frames = max(1, int(round(step_seconds * source_fps)))

    frames: list[np.ndarray] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frames.append(_score_roi(frame))
    finally:
        capture.release()

    if not enabled or frame_count <= target_frames:
        return {
            "selected_start_seconds": round(start_frame / source_fps, 3),
            "selection_score": 0.0,
            "candidates": [],
        }

    candidates = []
    best_score = float("-inf")
    best_start = start_frame
    for candidate_start in range(start_frame, max_start_frame + 1, step_frames):
        window = frames[candidate_start : candidate_start + target_frames]
        if len(window) < target_frames:
            continue
        score = _window_score(window)
        candidate = {
            "start_seconds": round(candidate_start / source_fps, 3),
            "score": round(float(score), 4),
        }
        candidates.append(candidate)
        if score > best_score:
            best_score = score
            best_start = candidate_start

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {
        "selected_start_seconds": round(best_start / source_fps, 3),
        "selection_score": round(float(best_score if best_score != float("-inf") else 0.0), 4),
        "candidates": candidates[:5],
    }


def _score_roi(frame: np.ndarray) -> np.ndarray:
    height, width = frame.shape[:2]
    top = int(height * 0.38)
    left = int(width * 0.12)
    right = int(width * 0.88)
    roi = frame[top:, left:right]
    return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)


def _window_score(gray_frames: list[np.ndarray]) -> float:
    sharpness_values = []
    contrast_values = []
    stability_values = []
    previous = None
    for gray in gray_frames:
        sharpness_values.append(cv2.Laplacian(gray, cv2.CV_32F).var() / 1000.0)
        contrast_values.append(float(gray.std()) / 64.0)
        if previous is not None:
            diff = cv2.absdiff(previous, gray)
            stability_values.append(1.0 / (1.0 + (float(diff.mean()) / 24.0)))
        previous = gray
    stability = sum(stability_values) / len(stability_values) if stability_values else 0.0
    sharpness = sum(sharpness_values) / len(sharpness_values)
    contrast = sum(contrast_values) / len(contrast_values)
    return (sharpness * 0.48) + (contrast * 0.24) + (stability * 0.28)


def _write_clip_slice(
    writer: cv2.VideoWriter,
    clip_path: Path,
    subtitle: str,
    draw_subtitles: bool,
    output_size: tuple[int, int],
    target_frames: int,
    start_offset_seconds: float,
) -> int:
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open Seedance clip: {clip_path}")

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 24.0)
    start_frame = max(0, int(round(start_offset_seconds * source_fps)))
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    written = 0
    try:
        while written < target_frames:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[1] != output_size[0] or frame.shape[0] != output_size[1]:
                frame = cv2.resize(frame, output_size)
            if draw_subtitles and subtitle:
                frame = _draw_bottom_subtitle(frame, subtitle)
            writer.write(frame)
            written += 1
    finally:
        capture.release()
    return written


def _draw_bottom_subtitle(frame: np.ndarray, text: str) -> np.ndarray:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    width, height = image.size
    font = _load_font(max(30, int(width * 0.052)))
    lines = _wrap_text(text, max_chars=14)
    line_height = int(font.size * 1.28) if hasattr(font, "size") else 42
    block_height = line_height * len(lines)
    y = height - block_height - int(height * 0.08)

    for index, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font, stroke_width=3)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        draw.text(
            (x, y + index * line_height),
            line,
            font=font,
            fill=(255, 255, 255),
            stroke_width=3,
            stroke_fill=(20, 20, 20),
        )
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _write_srt(path: Path, timeline: list[dict[str, Any]]) -> None:
    lines: list[str] = []
    cursor = 0.0
    for index, item in enumerate(timeline, start=1):
        duration = float(item.get("seconds", 0.0))
        start = cursor
        end = cursor + duration
        text = str(item.get("subtitle", "")).strip()
        if not text:
            cursor = end
            continue
        lines.extend(
            [
                str(index),
                f"{_format_srt_time(start)} --> {_format_srt_time(end)}",
                text,
                "",
            ]
        )
        cursor = end
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _write_voiceover_script(path: Path, timeline: list[dict[str, Any]]) -> None:
    lines = ["# Voiceover", ""]
    cursor = 0.0
    for item in timeline:
        duration = float(item.get("seconds", 0.0))
        end = cursor + duration
        source_texts = " / ".join(item.get("source_ocr_texts", []))
        lines.extend(
            [
                f"- scene {item['scene_index']} [{cursor:.3f}s - {end:.3f}s]",
                f"  subtitle: {item.get('subtitle', '')}",
                f"  voiceover: {item.get('voiceover', '')}",
                f"  source_segment_index: {item.get('source_segment_index', '-')}",
                f"  source_role: {item.get('source_role', '-')}",
                f"  hot_reference_texts: {source_texts or '-'}",
            ]
        )
        cursor = end
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_delivery_notes(path: Path, timeline: list[dict[str, Any]], output_file: Path) -> None:
    lines = [
        "# Delivery Notes",
        "",
        f"- Preview video: `{output_file.name}`",
        f"- Scenes: {', '.join(str(item['scene_index']) for item in timeline)}",
        "- Subtitle file is generated as sidecar `.srt`.",
        "- Voiceover lines are generated as sidecar `.txt`.",
        "- Audio is not muxed into the mp4 in the current environment.",
        "",
        "## Scene Summary",
        "",
    ]
    for item in timeline:
        source_texts = " / ".join(item.get("source_ocr_texts", []))
        lines.append(
            f"- scene {item['scene_index']}: start={item['selected_start_seconds']}s, "
            f"subtitle={item.get('subtitle', '')}, source_segment={item.get('source_segment_index') or '-'}, "
            f"source_role={item.get('source_role') or '-'}, "
            f"hot_reference_texts={source_texts or '-'}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _synthesize_voiceover_wav(output_path: Path, timeline: list[dict[str, Any]]) -> str:
    if os.name != "nt":
        return "unsupported_os"
    voice_lines = [str(item.get("voiceover", "")).strip() for item in timeline if item.get("voiceover")]
    if not voice_lines:
        return "no_voiceover_lines"

    payload = output_path.with_suffix(".tts.json")
    script = output_path.with_suffix(".tts.ps1")
    log_file = output_path.with_suffix(".tts.log")
    payload.write_text(json.dumps({"lines": voice_lines}, ensure_ascii=False, indent=2), encoding="utf-8")
    script.write_text(
        "\n".join(
            [
                "Add-Type -AssemblyName System.Speech",
                f"$payload = Get-Content -LiteralPath '{payload}' -Raw -Encoding UTF8 | ConvertFrom-Json",
                "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer",
                "try {",
                "  $culture = [System.Globalization.CultureInfo]::GetCultureInfo('zh-CN')",
                "  $synth.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::NotSet, [System.Speech.Synthesis.VoiceAge]::NotSet, 0, $culture)",
                "} catch { }",
                f"$synth.SetOutputToWaveFile('{output_path}')",
                "$builder = New-Object System.Speech.Synthesis.PromptBuilder",
                "foreach ($line in $payload.lines) {",
                "  if ([string]::IsNullOrWhiteSpace($line)) { continue }",
                "  $builder.AppendText($line)",
                "  $builder.AppendBreak([TimeSpan]::FromMilliseconds(350))",
                "}",
                "$synth.Speak($builder)",
                "$synth.Dispose()",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        log_file.write_text((result.stdout or "") + ("\n" + result.stderr if result.stderr else ""), encoding="utf-8")
    except subprocess.CalledProcessError as exc:
        log_file.write_text(
            "\n".join(
                [
                    f"returncode={exc.returncode}",
                    "[stdout]",
                    exc.stdout or "",
                    "[stderr]",
                    exc.stderr or "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return "tts_failed"
    except Exception as exc:
        log_file.write_text(f"{type(exc).__name__}: {exc}\n", encoding="utf-8")
        return "tts_failed"
    return "succeeded" if output_path.exists() else "tts_failed"


def _choose_text(*values: Any) -> str:
    for value in values:
        text = _normalize_text(value)
        if text:
            return text
    return ""


def _coerce_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _normalize_text_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    normalized: list[str] = []
    for value in values:
        text = _normalize_text(value)
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    repaired = _repair_mojibake_text(text)
    return repaired.strip()


def _repair_mojibake_text(text: str) -> str:
    if not _looks_like_utf8_mojibake(text):
        return text
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except UnicodeError:
        return text
    return repaired if _text_quality_score(repaired) >= _text_quality_score(text) else text


def _looks_like_utf8_mojibake(text: str) -> bool:
    hints = ("å", "ç", "é", "è", "æ", "ä", "ï", "â", "€", "™", "œ", "ž", "ƒ")
    return any(hint in text for hint in hints)


def _text_quality_score(text: str) -> int:
    cjk_count = sum(1 for char in text if "\u4e00" <= char <= "\u9fff")
    mojibake_penalty = sum(text.count(marker) for marker in ("å", "ç", "é", "è", "æ", "ä", "ï", "â"))
    return (cjk_count * 4) - mojibake_penalty


def _format_srt_time(seconds: float) -> str:
    total_ms = int(round(seconds * 1000))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines[:2]


def _probe_video(path: Path) -> dict[str, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Cannot probe video dimensions: {path}")
    return {"width": width, "height": height}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()
