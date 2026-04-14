"""本地视频抽帧与粗切片能力。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2

from gemeiqi.ocr import recognize_images, subtitle_texts, unique_texts
from gemeiqi.repository import dump_json
from gemeiqi.template_editor import write_template_editor_markdown


@dataclass(frozen=True)
class VideoProbe:
    """视频基础信息。"""

    path: Path
    fps: float
    frame_count: int
    duration_seconds: float
    width: int
    height: int


@dataclass(frozen=True)
class SampledFrame:
    """已抽取的关键帧信息。"""

    index: int
    frame_number: int
    timestamp_seconds: float
    image_path: Path
    diff_score: float


def analyze_local_video(
    video_path: Path,
    output_dir: Path,
    sample_id: str = "vs_local_001",
    sample_interval_seconds: float = 1.0,
    scene_threshold: float = 18.0,
    min_segment_seconds: float = 1.0,
    enable_ocr: bool = True,
) -> dict[str, Any]:
    """对本地视频执行抽帧、粗切片，并写入可查看结果。"""

    probe = probe_video(video_path)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sampled_frames = extract_sampled_frames(
        video_path=video_path,
        frames_dir=frames_dir,
        sample_interval_seconds=sample_interval_seconds,
    )
    segments = build_segments(
        sampled_frames=sampled_frames,
        duration_seconds=probe.duration_seconds,
        scene_threshold=scene_threshold,
        min_segment_seconds=min_segment_seconds,
    )
    export_segment_clips(
        video_path=video_path,
        output_dir=output_dir,
        probe=probe,
        segments=segments,
    )
    export_segment_review_frames(
        video_path=video_path,
        output_dir=output_dir,
        probe=probe,
        segments=segments,
    )
    if enable_ocr:
        recognize_segment_texts(output_dir=output_dir, segments=segments)

    result = {
        "video": {
            "path": str(video_path),
            "fps": round(probe.fps, 3),
            "frame_count": probe.frame_count,
            "duration_seconds": round(probe.duration_seconds, 3),
            "width": probe.width,
            "height": probe.height,
        },
        "settings": {
            "sample_interval_seconds": sample_interval_seconds,
            "scene_threshold": scene_threshold,
            "min_segment_seconds": min_segment_seconds,
            "enable_ocr": enable_ocr,
        },
        "frames": [_frame_to_dict(frame, output_dir) for frame in sampled_frames],
        "segments": segments,
    }

    video_analysis_draft = build_video_analysis_draft(result=result, sample_id=sample_id)
    content_template_draft = build_content_template_draft(video_analysis_draft)

    output_dir.mkdir(parents=True, exist_ok=True)
    dump_json(output_dir / "analysis.json", result)
    dump_json(output_dir / "video_analysis_draft.json", video_analysis_draft)
    dump_json(output_dir / "content_template_draft.json", content_template_draft)
    write_preview_html(output_dir / "preview.html", result)
    write_annotation_markdown(output_dir / "segments_annotation.md", video_analysis_draft)
    write_template_markdown(output_dir / "template_summary.md", content_template_draft)
    write_template_editor_markdown(output_dir / "template_editor.md", content_template_draft)
    return result


def probe_video(video_path: Path) -> VideoProbe:
    """读取视频基础信息。"""

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法打开视频：{video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()

    duration_seconds = frame_count / fps if fps > 0 else 0
    return VideoProbe(
        path=video_path,
        fps=fps,
        frame_count=frame_count,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
    )


def extract_sampled_frames(
    video_path: Path,
    frames_dir: Path,
    sample_interval_seconds: float,
) -> list[SampledFrame]:
    """按固定时间间隔抽取视频帧。"""

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法打开视频：{video_path}")

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    if fps <= 0:
        capture.release()
        raise ValueError(f"无法读取视频帧率：{video_path}")

    frame_step = max(1, int(round(fps * sample_interval_seconds)))
    sampled_frames: list[SampledFrame] = []
    previous_small_gray = None
    frame_number = 0
    sample_index = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        if frame_number % frame_step == 0:
            timestamp_seconds = frame_number / fps
            image_name = f"frame_{sample_index:04d}_{timestamp_seconds:06.2f}s.jpg"
            image_path = frames_dir / image_name
            cv2.imwrite(str(image_path), frame)

            small_gray = _small_gray(frame)
            diff_score = _frame_diff(previous_small_gray, small_gray)
            previous_small_gray = small_gray

            sampled_frames.append(
                SampledFrame(
                    index=sample_index,
                    frame_number=frame_number,
                    timestamp_seconds=timestamp_seconds,
                    image_path=image_path,
                    diff_score=diff_score,
                )
            )
            sample_index += 1

        frame_number += 1

    capture.release()
    return sampled_frames


def build_segments(
    sampled_frames: list[SampledFrame],
    duration_seconds: float,
    scene_threshold: float,
    min_segment_seconds: float,
) -> list[dict[str, Any]]:
    """根据相邻抽样帧差异生成粗切片。"""

    if not sampled_frames:
        return []

    boundaries = [sampled_frames[0]]
    last_boundary_time = sampled_frames[0].timestamp_seconds
    for frame in sampled_frames[1:]:
        enough_gap = frame.timestamp_seconds - last_boundary_time >= min_segment_seconds
        if frame.diff_score >= scene_threshold and enough_gap:
            boundaries.append(frame)
            last_boundary_time = frame.timestamp_seconds

    segments: list[dict[str, Any]] = []
    for index, boundary in enumerate(boundaries):
        next_start = (
            boundaries[index + 1].timestamp_seconds
            if index + 1 < len(boundaries)
            else duration_seconds
        )
        role = _guess_segment_role(index, len(boundaries))
        segments.append(
            {
                "index": index + 1,
                "start": round(boundary.timestamp_seconds, 3),
                "end": round(max(next_start, boundary.timestamp_seconds), 3),
                "duration_seconds": round(max(next_start - boundary.timestamp_seconds, 0), 3),
                "role_guess": role,
                "cover_frame": _relative_frame_path(boundary.image_path),
                "boundary_diff_score": round(boundary.diff_score, 3),
                "manual_review_required": True,
                "annotation_hints": _annotation_hints(role),
                "notes": "自动粗切片结果，需要人工确认片段角色和卖点。",
            }
        )

    return segments


def export_segment_review_frames(
    video_path: Path,
    output_dir: Path,
    probe: VideoProbe,
    segments: list[dict[str, Any]],
) -> None:
    """为每个片段导出起始、中间、结束复核图。"""

    review_dir = output_dir / "segment_frames"
    review_dir.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法打开视频：{video_path}")

    for segment in segments:
        timestamps = _review_timestamps(segment)
        review_frames = []
        for label, timestamp in timestamps:
            frame_path = review_dir / (
                f"segment_{segment['index']:04d}_{label}_{timestamp:06.2f}s.jpg"
            )
            if _save_frame_at(capture, frame_path, timestamp, probe.fps):
                review_frames.append(
                    {
                        "label": label,
                        "timestamp_seconds": round(timestamp, 3),
                        "image_path": f"segment_frames/{frame_path.name}",
                    }
                )
        segment["review_frames"] = review_frames

    capture.release()


def recognize_segment_texts(output_dir: Path, segments: list[dict[str, Any]]) -> None:
    """识别每个片段复核图中的文字。"""

    for segment in segments:
        image_paths = [
            output_dir / frame["image_path"]
            for frame in segment.get("review_frames", [])
            if frame.get("image_path")
        ]
        ocr_results = recognize_images(image_paths)
        flat_items = []
        for result in ocr_results:
            relative_image_path = str(Path(result["image_path"]).relative_to(output_dir))
            for text_item in result["texts"]:
                flat_items.append(
                    {
                        "image_path": relative_image_path,
                        "text": text_item["text"],
                        "confidence": text_item["confidence"],
                        "box": text_item["box"],
                    }
                )

        segment["ocr_items"] = flat_items
        segment["ocr_texts_raw"] = unique_texts(flat_items)
        segment["ocr_texts"] = subtitle_texts(flat_items)


def export_segment_clips(
    video_path: Path,
    output_dir: Path,
    probe: VideoProbe,
    segments: list[dict[str, Any]],
) -> None:
    """把粗切片导出成独立视频片段。"""

    clips_dir = output_dir / "segments"
    clips_dir.mkdir(parents=True, exist_ok=True)

    for segment in segments:
        clip_name = f"segment_{segment['index']:04d}_{segment['start']:06.2f}s.mp4"
        clip_path = clips_dir / clip_name
        _write_clip(video_path=video_path, clip_path=clip_path, probe=probe, segment=segment)
        segment["clip_path"] = f"segments/{clip_name}"


def _review_timestamps(segment: dict[str, Any]) -> list[tuple[str, float]]:
    start = float(segment["start"])
    end = float(segment["end"])
    duration = max(end - start, 0.001)
    return [
        ("start", start),
        ("middle", start + duration / 2),
        ("end", max(start, end - 0.08)),
    ]


def _save_frame_at(
    capture: Any,
    image_path: Path,
    timestamp_seconds: float,
    fps: float,
) -> bool:
    frame_number = max(0, int(round(timestamp_seconds * fps)))
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ok, frame = capture.read()
    if not ok:
        return False
    return bool(cv2.imwrite(str(image_path), frame))


def _write_clip(
    video_path: Path,
    clip_path: Path,
    probe: VideoProbe,
    segment: dict[str, Any],
) -> None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"无法打开视频：{video_path}")

    start_frame = max(0, int(round(segment["start"] * probe.fps)))
    end_frame = max(start_frame + 1, int(round(segment["end"] * probe.fps)))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(clip_path), fourcc, probe.fps, (probe.width, probe.height))
    if not writer.isOpened():
        capture.release()
        raise ValueError(f"无法写入视频片段：{clip_path}")

    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    current_frame = start_frame
    while current_frame < end_frame:
        ok, frame = capture.read()
        if not ok:
            break
        writer.write(frame)
        current_frame += 1

    writer.release()
    capture.release()


def write_preview_html(path: Path, result: dict[str, Any]) -> None:
    """写入可直接打开的 HTML 预览页。"""

    video = result["video"]
    settings = result["settings"]
    frame_cards = "\n".join(_frame_card(frame) for frame in result["frames"])
    segment_rows = "\n".join(_segment_row(segment) for segment in result["segments"])

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>本地视频抽帧与粗切片预览</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      color: #202124;
      background: #f6f7f9;
    }}
    header {{ padding: 24px; background: #ffffff; border-bottom: 1px solid #dfe3e8; }}
    main {{ padding: 24px; }}
    h1, h2 {{ margin: 0 0 12px; }}
    .meta {{ line-height: 1.8; }}
    table {{ width: 100%; border-collapse: collapse; background: #ffffff; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #dfe3e8; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f5; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 12px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #dfe3e8;
      border-radius: 6px;
      overflow: hidden;
    }}
    .card img {{ display: block; width: 100%; height: auto; }}
    .card div {{ padding: 8px; font-size: 13px; line-height: 1.5; }}
  </style>
</head>
<body>
  <header>
    <h1>本地视频抽帧与粗切片预览</h1>
    <div class="meta">
      视频：{video["path"]}<br>
      时长：{video["duration_seconds"]} 秒，帧率：{video["fps"]}，
      尺寸：{video["width"]}x{video["height"]}<br>
      抽帧间隔：{settings["sample_interval_seconds"]} 秒，切片阈值：{settings["scene_threshold"]}
    </div>
  </header>
  <main>
    <h2>粗切片</h2>
    <table>
      <thead>
        <tr>
          <th>序号</th>
          <th>时间段</th>
          <th>时长</th>
          <th>角色猜测</th>
          <th>边界差异</th>
          <th>封面帧</th>
          <th>片段视频</th>
          <th>OCR 字幕</th>
          <th>标注重点</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        {segment_rows}
      </tbody>
    </table>
    <h2>抽样帧</h2>
    <div class="grid">
      {frame_cards}
    </div>
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def build_video_analysis_draft(result: dict[str, Any], sample_id: str) -> dict[str, Any]:
    """根据粗切片结果生成可人工标注的视频解析草稿。"""

    video = result["video"]
    segments = []
    for segment in result["segments"]:
        role = _normalize_role(segment["role_guess"])
        segments.append(
            {
                "index": segment["index"],
                "start": segment["start"],
                "end": segment["end"],
                "duration_seconds": segment["duration_seconds"],
                "role": role,
                "visual_focus": "",
                "selling_point": _infer_segment_selling_point(segment),
                "copywriting": " / ".join(segment.get("ocr_texts", [])),
                "reusable": None,
                "cover_frame": segment["cover_frame"],
                "clip_path": segment.get("clip_path"),
                "review_frames": segment.get("review_frames", []),
                "ocr_items": segment.get("ocr_items", []),
                "ocr_texts_raw": segment.get("ocr_texts_raw", []),
                "ocr_texts": segment.get("ocr_texts", []),
                "annotation_hints": segment.get("annotation_hints", []),
                "review_status": "pending_manual_review",
                "notes": "请人工确认该片段的真实画面内容、卖点和可复用性。",
            }
        )

    primary_selling_points = _infer_primary_selling_points(segments)
    return {
        "id": f"analysis_draft_{sample_id}",
        "sample_id": sample_id,
        "source_video": video["path"],
        "summary": _infer_summary(segments),
        "hook_type": _infer_hook_type(segments),
        "primary_selling_points": primary_selling_points,
        "segments": segments,
        "trace": {
            "source": "gemeiqi.video_processing.analyze_local_video",
            "analysis_file": "analysis.json",
            "preview_file": "preview.html",
            "draft_type": "manual_annotation_seed",
        },
    }


def write_annotation_markdown(path: Path, draft: dict[str, Any]) -> None:
    """写入方便人工标注的 Markdown 表格。"""

    lines = [
        "# 视频片段人工标注表",
        "",
        f"- 样本 ID：`{draft['sample_id']}`",
        f"- 来源视频：`{draft['source_video']}`",
        "",
        "请逐段补充：画面重点、卖点、文案/字幕、是否可复用。",
        "",
        "| 序号 | 时间段 | 初始角色 | 片段视频 | OCR 字幕 | 标注重点 | 画面重点 | 卖点 | 可复用 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for segment in draft["segments"]:
        clip = segment.get("clip_path") or ""
        lines.append(
            "| "
            f"{segment['index']} | "
            f"{segment['start']}s-{segment['end']}s | "
            f"{segment['role']} | "
            f"`{clip}` | "
            f"{_join_markdown_hints(segment.get('ocr_texts', []))} | "
            f"{_join_markdown_hints(segment.get('annotation_hints', []))} |  | "
            f"{segment.get('selling_point', '')} |  |"
        )

    lines.extend(
        [
            "",
            "## 片段角色建议",
            "",
            "- `hook`：开头钩子，负责制造停留理由。",
            "- `product_or_try_on`：商品全貌或上脚展示。",
            "- `detail_or_selling_point`：细节证明或卖点解释。",
            "- `transition_or_scene`：场景、穿搭、转场或补充证明。",
            "- `closing`：收尾强化、购买理由或行动提示。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_content_template_draft(video_analysis_draft: dict[str, Any]) -> dict[str, Any]:
    """根据视频解析草稿生成模板草稿。"""

    segments = video_analysis_draft.get("segments", [])
    selling_point_order = _infer_primary_selling_points(segments)
    scene_structure = []
    for segment in segments:
        scene_structure.append(
            {
                "role": segment["role"],
                "duration_seconds": segment["duration_seconds"],
                "goal": _infer_scene_goal(segment),
                "source_segment_index": segment["index"],
                "reusable_hint": _infer_reusable_hint(segment),
                "ocr_examples": segment.get("ocr_texts", [])[:3],
            }
        )

    draft_id = f"tpl_draft_{video_analysis_draft['sample_id']}"
    return {
        "id": draft_id,
        "name": _infer_template_name(video_analysis_draft),
        "version": "0.1.0-draft",
        "source_analysis_ids": [video_analysis_draft["id"]],
        "platforms": ["douyin"],
        "hook_type": video_analysis_draft.get("hook_type", ""),
        "scene_structure": scene_structure,
        "selling_point_order": selling_point_order,
        "copywriting_style": _infer_copywriting_style(video_analysis_draft),
        "product_variables": [
            "shoe_type",
            "primary_selling_points",
            "target_scenarios",
            "material",
            "detail_features",
            "promotion_message",
        ],
        "template_summary": video_analysis_draft.get("summary", ""),
        "reuse_notes": [
            "优先复用片段结构，不直接照搬原视频文案。",
            "舒适、场景、穿脱和促销表达可按商品属性替换。",
            "收尾促销信息需要根据实际活动更新时间和价格。",
        ],
        "review_status": "pending_manual_review",
    }


def write_template_markdown(path: Path, template_draft: dict[str, Any]) -> None:
    """写入模板草稿摘要。"""

    lines = [
        "# 内容模板草稿",
        "",
        f"- 模板 ID：`{template_draft['id']}`",
        f"- 模板名：{template_draft['name']}",
        f"- 版本：`{template_draft['version']}`",
        f"- 平台：`{', '.join(template_draft['platforms'])}`",
        f"- 钩子类型：`{template_draft['hook_type']}`",
        f"- 卖点顺序：{'、'.join(template_draft['selling_point_order']) or '待人工补充'}",
        "",
        f"模板摘要：{template_draft.get('template_summary', '')}",
        "",
        "## 片段结构",
        "",
        "| 顺序 | 角色 | 时长 | 目标 | 可复用提示 | OCR 示例 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for scene in template_draft["scene_structure"]:
        lines.append(
            "| "
            f"{scene['source_segment_index']} | "
            f"{scene['role']} | "
            f"{scene['duration_seconds']}s | "
            f"{scene['goal']} | "
            f"{scene['reusable_hint']} | "
            f"{_join_markdown_hints(scene.get('ocr_examples', []))} |"
        )

    lines.extend(
        [
            "",
            "## 商品变量位",
            "",
        ]
    )
    for field in template_draft["product_variables"]:
        lines.append(f"- `{field}`")

    lines.extend(
        [
            "",
            "## 复用说明",
            "",
        ]
    )
    for note in template_draft.get("reuse_notes", []):
        lines.append(f"- {note}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _small_gray(frame: Any) -> Any:
    resized = cv2.resize(frame, (96, 96))
    return cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)


def _frame_diff(previous: Any, current: Any) -> float:
    if previous is None:
        return 0.0
    diff = cv2.absdiff(previous, current)
    return float(diff.mean())


def _guess_segment_role(index: int, total: int) -> str:
    if index == 0:
        return "hook"
    if index == total - 1:
        return "closing"
    if index == 1:
        return "product_or_try_on"
    if index == 2:
        return "detail_or_selling_point"
    return "transition_or_scene"


def _normalize_role(role_guess: str) -> str:
    return role_guess


def _annotation_hints(role: str) -> list[str]:
    common = [
        "确认是否出现鞋款主体",
        "记录画面中可复用的镜头结构",
    ]
    if role == "hook":
        return [
            "判断开头是否有痛点、反差或强利益点",
            "记录字幕或口播第一句话",
            "判断这个开头是否能迁移到自家 SKU",
        ]
    if role == "product_or_try_on":
        return [
            "标注是商品全貌还是上脚展示",
            "记录鞋型、鞋头、鞋跟、颜色是否清楚",
            "判断上脚比例是否自然",
        ]
    if role == "detail_or_selling_point":
        return [
            "标注具体细节：鞋面、鞋底、鞋跟、鞋扣或材质",
            "记录该细节对应的卖点",
            "判断是否需要实拍而不是生成",
        ]
    if role == "closing":
        return [
            "记录收尾是否强化人群、场景或购买理由",
            "判断是否有行动提示",
            "判断收尾是否可作为模板固定结构",
        ]
    return common + [
        "判断该段是转场、穿搭、场景证明还是补充卖点",
        "记录该段是否影响转化",
    ]


def _join_markdown_hints(hints: list[str]) -> str:
    return "<br>".join(hints)


def _infer_scene_goal(segment: dict[str, Any]) -> str:
    role = segment.get("role", "")
    selling_point = segment.get("selling_point", "")
    if role == "hook":
        return "快速建立停留理由，引出核心利益点。"
    if role == "product_or_try_on":
        return "展示商品主体或上脚状态，帮助用户建立直观感受。"
    if role == "detail_or_selling_point":
        return f"用细节证明卖点：{selling_point or '待人工补充'}。"
    if role == "closing":
        return "收束内容，强化购买理由、活动信息或行动提示。"
    if selling_point:
        return f"补充证明或扩展卖点：{selling_point}。"
    return "承接前后片段，补充场景、情绪或视觉节奏。"


def _infer_reusable_hint(segment: dict[str, Any]) -> str:
    role = segment.get("role", "")
    selling_point = segment.get("selling_point", "")
    if role == "closing":
        return "结构可复用，促销文案和价格信息必须替换。"
    if role == "hook":
        return "保留开头结构，替换为更贴合目标 SKU 的钩子表达。"
    if selling_point:
        return f"可复用该段结构，但要按商品重写“{selling_point}”表达。"
    return "保留镜头结构，按商品和平台风格重写内容。"


def _infer_template_name(video_analysis_draft: dict[str, Any]) -> str:
    points = video_analysis_draft.get("primary_selling_points", [])
    if not points:
        return "女鞋短视频模板草稿"
    return f"女鞋{'/'.join(points[:3])}型模板"


def _infer_copywriting_style(video_analysis_draft: dict[str, Any]) -> dict[str, Any]:
    segments = video_analysis_draft.get("segments", [])
    keywords = []
    seen = set()
    for segment in segments:
        for text in segment.get("ocr_texts", []):
            if len(text) > 14:
                continue
            if text in seen:
                continue
            keywords.append(text)
            seen.add(text)
            if len(keywords) >= 8:
                break
        if len(keywords) >= 8:
            break

    return {
        "tone": "口语化种草",
        "pace": "中快节奏",
        "keywords": keywords,
    }


def _infer_segment_selling_point(segment: dict[str, Any]) -> str:
    text = " ".join(segment.get("ocr_texts", []))
    if any(keyword in text for keyword in ("立减", "券", "到手价")):
        return "促销转化"
    if any(keyword in text for keyword in ("舒适", "不会累", "柔软")):
        return "舒适久走"
    if any(keyword in text for keyword in ("魔术贴", "穿脱", "省心")):
        return "穿脱方便"
    if any(keyword in text for keyword in ("通勤", "日常", "休闲", "出行")):
        return "场景百搭"
    if any(keyword in text for keyword in ("颜值", "好搭子", "玛丽珍")):
        return "风格颜值"
    return ""


def _infer_primary_selling_points(segments: list[dict[str, Any]]) -> list[str]:
    points = []
    seen = set()
    for segment in segments:
        point = segment.get("selling_point")
        if not point or point in seen:
            continue
        points.append(point)
        seen.add(point)
    return points


def _infer_hook_type(segments: list[dict[str, Any]]) -> str:
    if not segments:
        return ""
    first_text = " ".join(segments[0].get("ocr_texts", []))
    if any(keyword in first_text for keyword in ("偏爱", "舒适", "不妨")):
        return "preference_or_comfort_hook"
    if any(keyword in first_text for keyword in ("痛", "累", "不舒服")):
        return "pain_point_hook"
    return ""


def _infer_summary(segments: list[dict[str, Any]]) -> str:
    points = _infer_primary_selling_points(segments)
    if not points:
        return "自动生成的视频解析草稿，等待人工补充画面重点、卖点和可复用性。"
    return f"自动草稿识别到主要表达方向：{'、'.join(points)}。请人工复核。"


def _frame_to_dict(frame: SampledFrame, output_dir: Path) -> dict[str, Any]:
    return {
        "index": frame.index,
        "frame_number": frame.frame_number,
        "timestamp_seconds": round(frame.timestamp_seconds, 3),
        "image_path": str(frame.image_path.relative_to(output_dir)),
        "diff_score": round(frame.diff_score, 3),
    }


def _relative_frame_path(path: Path) -> str:
    return f"frames/{path.name}"


def _frame_card(frame: dict[str, Any]) -> str:
    return (
        '<div class="card">'
        f'<img src="{frame["image_path"]}" alt="frame {frame["index"]}">'
        f'<div>#{frame["index"]}<br>{frame["timestamp_seconds"]}s'
        f'<br>差异：{frame["diff_score"]}</div>'
        "</div>"
    )


def _segment_row(segment: dict[str, Any]) -> str:
    clip_html = (
        f'<video src="{segment["clip_path"]}" controls width="220"></video>'
        if segment.get("clip_path")
        else ""
    )
    review_frames_html = "".join(
        f'<img src="{frame["image_path"]}" width="90" alt="{frame["label"]}">'
        for frame in segment.get("review_frames", [])
    )
    ocr_html = "<br>".join(segment.get("ocr_texts", []))
    hints_html = "<br>".join(segment.get("annotation_hints", []))
    return (
        "<tr>"
        f"<td>{segment['index']}</td>"
        f"<td>{segment['start']}s - {segment['end']}s</td>"
        f"<td>{segment['duration_seconds']}s</td>"
        f"<td>{segment['role_guess']}</td>"
        f"<td>{segment['boundary_diff_score']}</td>"
        "<td>"
        f"<img src=\"{segment['cover_frame']}\" "
        f"width=\"120\" alt=\"segment {segment['index']}\">"
        f"<div>{review_frames_html}</div>"
        "</td>"
        f"<td>{clip_html}</td>"
        f"<td>{ocr_html}</td>"
        f"<td>{hints_html}</td>"
        f"<td>{segment['notes']}</td>"
        "</tr>"
    )
