"""基于脚本执行单合成视频草稿。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from gemeiqi.repository import dump_json


def render_script_video(
    analysis: dict[str, Any],
    script_output: dict[str, Any],
    product: dict[str, Any],
    analysis_dir: Path,
    output_dir: Path,
    fps: float = 25.0,
) -> dict[str, Any]:
    """根据切片和脚本执行单合成一条视频草稿。"""

    timeline = build_timeline(analysis=analysis, script_output=script_output)
    if not timeline:
        raise ValueError("没有可用于渲染的视频片段。")

    first_clip = analysis_dir / timeline[0]["clip_path"]
    probe = _probe_clip(first_clip)
    render_dir = output_dir
    render_dir.mkdir(parents=True, exist_ok=True)

    video_path = render_dir / "draft_video.mp4"
    writer = cv2.VideoWriter(
        str(video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (probe["width"], probe["height"]),
    )
    if not writer.isOpened():
        raise ValueError(f"无法写入视频：{video_path}")

    title_card_frames = max(1, int(round(fps * 1.5)))
    title_card = render_title_card(
        width=probe["width"],
        height=probe["height"],
        product_name=product["name"],
        title=script_output["title_options"][0],
    )
    for _ in range(title_card_frames):
        writer.write(title_card)

    for item in timeline:
        _write_scene_clip(
            writer=writer,
            clip_path=analysis_dir / item["clip_path"],
            scene=item,
            fps=fps,
            size=(probe["width"], probe["height"]),
            product_name=product["name"],
        )

    writer.release()

    render_plan = {
        "product_id": product["id"],
        "product_name": product["name"],
        "script_id": script_output["id"],
        "output_video": str(video_path),
        "title_card_seconds": round(title_card_frames / fps, 3),
        "timeline": timeline,
    }
    dump_json(render_dir / "render_plan.json", render_plan)
    return render_plan


def build_timeline(analysis: dict[str, Any], script_output: dict[str, Any]) -> list[dict[str, Any]]:
    """把脚本分镜映射到已切好的片段视频。"""

    segment_map = {segment["index"]: segment for segment in analysis.get("segments", [])}
    timeline = []
    for scene in script_output.get("scenes", []):
        source_segment_index = scene.get("source_segment_index")
        segment = segment_map.get(source_segment_index)
        if not segment or not segment.get("clip_path"):
            continue
        timeline.append(
            {
                "scene_index": scene["index"],
                "source_segment_index": source_segment_index,
                "clip_path": segment["clip_path"],
                "duration_seconds": scene.get(
                    "duration_seconds",
                    segment.get("duration_seconds", 0),
                ),
                "role": scene["role"],
                "shot_type": scene.get("shot_type", ""),
                "subtitle": scene.get("subtitle_suggestion", ""),
                "narration": scene.get("narration_suggestion", ""),
                "selling_point": scene.get("selling_point", ""),
            }
        )
    return timeline


def render_title_card(width: int, height: int, product_name: str, title: str) -> np.ndarray:
    """渲染开场标题卡。"""

    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :] = (26, 24, 20)
    frame = _draw_text_box(
        frame,
        top_text=product_name,
        bottom_text=title,
        footer_text="AI 草稿视频 · 请人工复核",
    )
    return frame


def _write_scene_clip(
    writer: cv2.VideoWriter,
    clip_path: Path,
    scene: dict[str, Any],
    fps: float,
    size: tuple[int, int],
    product_name: str,
) -> None:
    capture = cv2.VideoCapture(str(clip_path))
    if not capture.isOpened():
        return

    limit_frames = max(1, int(round(scene["duration_seconds"] * fps)))
    written = 0
    while written < limit_frames:
        ok, frame = capture.read()
        if not ok:
            break
        if frame.shape[1] != size[0] or frame.shape[0] != size[1]:
            frame = cv2.resize(frame, size)
        frame = _overlay_scene_text(frame, scene=scene, product_name=product_name)
        writer.write(frame)
        written += 1

    capture.release()


def _overlay_scene_text(
    frame: np.ndarray,
    scene: dict[str, Any],
    product_name: str,
) -> np.ndarray:
    top = (
        f"{scene['scene_index']}. {scene['shot_type']} · "
        f"{scene['selling_point'] or scene['role']}"
    )
    bottom = scene.get("subtitle") or scene.get("narration") or product_name
    footer = f"片段 {scene['source_segment_index']} · {scene['role']}"
    return _draw_text_box(frame, top_text=top, bottom_text=bottom, footer_text=footer)


def _draw_text_box(
    frame: np.ndarray,
    top_text: str,
    bottom_text: str,
    footer_text: str,
) -> np.ndarray:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image)
    width, height = image.size

    draw.rectangle((0, 0, width, 70), fill=(0, 0, 0, 180))
    draw.rectangle((0, height - 140, width, height), fill=(0, 0, 0, 180))

    title_font = _load_font(28)
    text_font = _load_font(32)
    footer_font = _load_font(20)

    draw.text((24, 18), top_text, font=title_font, fill=(255, 255, 255))

    wrapped_bottom = _wrap_text(bottom_text, max_chars=20)
    for index, line in enumerate(wrapped_bottom):
        draw.text(
            (24, height - 122 + index * 36),
            line,
            font=text_font,
            fill=(255, 244, 214),
        )

    draw.text((24, height - 34), footer_text, font=footer_font, fill=(208, 208, 208))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    if not text:
        return [""]
    lines = []
    current = ""
    for char in text:
        current += char
        if len(current) >= max_chars:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    return lines[:2]


def _probe_clip(path: Path) -> dict[str, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"无法打开片段：{path}")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
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
