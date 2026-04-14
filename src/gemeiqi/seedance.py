"""Seedance 视频生成计划与任务提交。"""

from __future__ import annotations

import json
import os
from base64 import b64encode
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from gemeiqi.paths import SAMPLES_DIR, project_path
from gemeiqi.repository import dump_json, load_json

DEFAULT_MODEL = "doubao-seedance-2-0-260128"
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "1080p"
TASKS_PATH = "/api/v3/contents/generations/tasks"
GENERATION_PROFILE_PRODUCT = "product_showcase"
GENERATION_PROFILE_TRYON = "model_tryon"
MAX_REFERENCE_IMAGE_CONTENT = 4
MAX_PRODUCT_REFERENCE_IMAGES = 2
TRYON_ROLES = {
    "hook",
    "product_or_try_on",
    "detail_or_selling_point",
    "transition_or_scene",
    "closing",
}

OFFICIAL_VIDEO_MODELS = {
    "doubao-seedance-1-0-lite-t2v-250428",
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-2-0-260128",
}


def resolve_reference_images(
    product: dict[str, Any],
    explicit_paths: list[str] | None = None,
) -> list[dict[str, Any]]:
    """解析商品参考图。"""

    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    explicit_paths = explicit_paths or []

    for index, path_value in enumerate(explicit_paths, start=1):
        path = _resolve_path(path_value)
        if not path.exists():
            raise FileNotFoundError(f"商品参考图不存在：{path}")
        path_key = str(path.resolve())
        if path_key in seen:
            continue
        seen.add(path_key)
        resolved.append(
            {
                "index": index,
                "asset_id": f"explicit_image_{index:02d}",
                "local_path": str(path),
                "source": "explicit_path",
            }
        )

    if resolved:
        return resolved

    sample_index = load_json(SAMPLES_DIR / "sample_assets.json")
    asset_map = {asset["id"]: asset for asset in sample_index.get("assets", [])}
    for asset_ref in product.get("asset_refs", []):
        asset = asset_map.get(asset_ref)
        if not asset or asset.get("kind") != "image":
            continue
        path = _resolve_path(asset["path"])
        if not path.exists():
            continue
        path_key = str(path.resolve())
        if path_key in seen:
            continue
        seen.add(path_key)
        resolved.append(
            {
                "index": len(resolved) + 1,
                "asset_id": asset["id"],
                "local_path": str(path),
                "source": "sample_asset",
            }
        )

    if not resolved:
        raise ValueError(f"商品 {product['id']} 没有可用参考图")
    return resolved


def build_seedance_plan(
    analysis: dict[str, Any],
    script_output: dict[str, Any],
    product: dict[str, Any],
    reference_images: list[dict[str, Any]],
    output_dir: Path,
    model: str = DEFAULT_MODEL,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str = DEFAULT_RESOLUTION,
    watermark: bool = False,
    public_reference_urls: list[str] | None = None,
    generation_profile: str = GENERATION_PROFILE_PRODUCT,
    template_adaptation: dict[str, Any] | None = None,
    analysis_dir: Path | None = None,
) -> dict[str, Any]:
    """基于脚本执行单构建 Seedance 任务计划。"""

    _validate_video_generation_model(model)
    _validate_generation_profile(generation_profile)

    segments_by_index = {
        segment["index"]: segment for segment in analysis.get("segments", []) if "index" in segment
    }
    merged_images = _merge_public_urls(reference_images, public_reference_urls or [])
    adaptations_by_index = _index_template_adaptations(template_adaptation)
    scenes: list[dict[str, Any]] = []

    for scene in script_output.get("scenes", []):
        source_segment = segments_by_index.get(scene.get("source_segment_index"))
        source_reference_frames = _resolve_source_reference_frames(source_segment, analysis_dir)
        template_scene = adaptations_by_index.get(scene["index"])
        generation_mode = _generation_mode(scene["role"], generation_profile)
        scene_prompt = _build_scene_prompt(
            scene,
            product,
            source_segment,
            aspect_ratio,
            resolution,
            generation_profile,
            template_scene,
            source_reference_frames,
        )
        negative_prompt = _build_negative_prompt(scene, product, template_scene)
        request_payload = _build_request_payload(
            model=model,
            prompt=scene_prompt,
            negative_prompt=negative_prompt,
            reference_images=merged_images,
            duration_seconds=scene.get("duration_seconds", 3.0),
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            watermark=watermark,
            generation_mode=generation_mode,
            source_reference_frames=source_reference_frames,
        )
        reference_image_order = _build_reference_image_order(
            product_images=merged_images,
            source_reference_frames=source_reference_frames,
            generation_mode=generation_mode,
        )
        scenes.append(
            {
                "scene_index": scene["index"],
                "role": scene["role"],
                "generation_profile": generation_profile,
                "generation_mode": generation_mode,
                "risk_level": _risk_level(scene["role"], generation_profile),
                "submit_recommended": _submit_recommended(scene["role"], generation_profile),
                "duration_seconds": scene.get("duration_seconds", 3.0),
                "subtitle_suggestion": scene.get("subtitle_suggestion", ""),
                "narration_suggestion": scene.get("narration_suggestion", ""),
                "prompt": scene_prompt,
                "negative_prompt": negative_prompt,
                "reference_images": merged_images,
                "source_reference_frames": source_reference_frames,
                "reference_image_order": reference_image_order,
                "source_hot_video": {
                    "video_path": analysis.get("video", {}).get("path", ""),
                    "segment_index": scene.get("source_segment_index"),
                    "clip_path": source_segment.get("clip_path") if source_segment else "",
                    "cover_frame": source_segment.get("cover_frame") if source_segment else "",
                },
                "template_adaptation": _compact_template_adaptation(template_scene),
                "script_trace": {
                    "script_id": script_output.get("id", ""),
                    "template_id": script_output.get("template_id", ""),
                    "product_id": script_output.get("product_id", ""),
                },
                "request_payload": request_payload,
            }
        )

    return {
        "id": f"seedance_plan_{product['id']}",
        "product_id": product["id"],
        "product_name": product["name"],
        "analysis_video": analysis.get("video", {}).get("path", ""),
        "script_id": script_output.get("id", ""),
        "template_id": script_output.get("template_id", ""),
        "model": model,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "watermark": watermark,
        "generation_profile": generation_profile,
        "template_adaptation_id": template_adaptation.get("id", "") if template_adaptation else "",
        "reference_images": merged_images,
        "segments": scenes,
        "trace": {
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": "gemeiqi.seedance.build_seedance_plan",
            "output_dir": str(output_dir),
        },
    }


def write_seedance_summary(path: Path, plan: dict[str, Any]) -> None:
    """写出 Seedance 任务摘要。"""

    lines = [
        "# Seedance 视频生成计划",
        "",
        f"- 商品：`{plan['product_id']}` {plan['product_name']}",
        f"- 模型：`{plan['model']}`",
        f"- 画幅：`{plan['aspect_ratio']}`",
        f"- 分辨率：`{plan['resolution']}`",
        f"- 爆款源视频：`{plan['analysis_video']}`",
        "",
        "## 参考图",
        "",
    ]
    for image in plan.get("reference_images", []):
        line = f"- `{image['asset_id']}` {image['local_path']}"
        if image.get("public_url"):
            line += f" -> {image['public_url']}"
        else:
            line += " -> 使用 data URL 内嵌提交"
        lines.append(line)

    lines.extend(
        [
            "",
            "## 分镜任务",
            "",
            "| 分镜 | 角色 | 方式 | 风险 | 建议提交 | 源片段 | 请求模板 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for segment in plan.get("segments", []):
        lines.append(
            "| "
            f"{segment['scene_index']} | "
            f"{segment['role']} | "
            f"{segment['generation_mode']} | "
            f"{segment['risk_level']} | "
            f"{'是' if segment['submit_recommended'] else '否'} | "
            f"{segment['source_hot_video'].get('segment_index') or ''} | "
            f"`request_templates/segment_{segment['scene_index']:04d}.json` |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_request_templates(output_dir: Path, plan: dict[str, Any]) -> None:
    """写出每个分镜的请求模板。"""

    request_dir = output_dir / "request_templates"
    request_dir.mkdir(parents=True, exist_ok=True)
    for segment in plan.get("segments", []):
        dump_json(
            request_dir / f"segment_{segment['scene_index']:04d}.json",
            segment["request_payload"],
        )


def submit_seedance_plan(
    plan: dict[str, Any],
    output_dir: Path,
    client: SeedanceClient,
    include_high_risk: bool = False,
    scene_indexes: list[int] | None = None,
) -> dict[str, Any]:
    """提交 Seedance 任务计划。"""

    tasks = []
    selected_scene_indexes = set(scene_indexes or [])
    for segment in plan.get("segments", []):
        if selected_scene_indexes and segment["scene_index"] not in selected_scene_indexes:
            tasks.append(
                {
                    "scene_index": segment["scene_index"],
                    "role": segment["role"],
                    "status": "skipped_not_selected",
                    "task_id": "",
                }
            )
            continue

        if not include_high_risk and not segment.get("submit_recommended", False):
            tasks.append(
                {
                    "scene_index": segment["scene_index"],
                    "role": segment["role"],
                    "status": "skipped_high_risk",
                    "task_id": "",
                }
            )
            continue

        payload = segment["request_payload"]
        _ensure_image_urls(payload)
        response = client.create_task(payload)
        tasks.append(
            {
                "scene_index": segment["scene_index"],
                "role": segment["role"],
                "status": _extract_task_status(response) or "submitted",
                "task_id": _extract_task_id(response),
                "response": response,
            }
        )

    result = {
        "plan_id": plan["id"],
        "submitted_at": datetime.now(UTC).isoformat(),
        "tasks": tasks,
    }
    dump_json(output_dir / "seedance_tasks.json", result)
    return result


def refresh_seedance_tasks(tasks_file: Path, client: SeedanceClient) -> dict[str, Any]:
    """刷新已提交任务状态。"""

    tasks_payload = load_json(tasks_file)
    refreshed_tasks = []
    for task in tasks_payload.get("tasks", []):
        task_id = task.get("task_id", "")
        if not task_id:
            refreshed_tasks.append(task)
            continue

        response = client.get_task(task_id)
        refreshed = dict(task)
        refreshed["status"] = _extract_task_status(response) or refreshed.get("status", "")
        refreshed["response"] = response
        refreshed_tasks.append(refreshed)

    result = dict(tasks_payload)
    result["checked_at"] = datetime.now(UTC).isoformat()
    result["tasks"] = refreshed_tasks
    dump_json(tasks_file, result)
    return result


class SeedanceClient:
    """Seedance 视频生成任务客户端。"""

    def __init__(self, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.tasks_url = _normalize_tasks_url(base_url)

    def create_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", self.tasks_url, payload)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._request_json("GET", f"{self.tasks_url}/{task_id}")

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=120) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Seedance API 请求失败：{exc.code} {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Seedance API 网络错误：{exc.reason}") from exc

        if not body:
            return {}
        return json.loads(body)


def build_client_from_env(base_url: str | None = None) -> SeedanceClient:
    """从环境变量构建客户端。"""

    api_key = os.environ.get("SEEDANCE_API_KEY") or os.environ.get("ARK_API_KEY")
    if not api_key:
        raise RuntimeError("未提供 Seedance API Key，请设置 SEEDANCE_API_KEY 或 ARK_API_KEY")
    resolved_base_url = (
        base_url
        or os.environ.get("SEEDANCE_API_BASE_URL")
        or os.environ.get("ARK_API_BASE_URL")
    )
    if not resolved_base_url:
        raise RuntimeError("未提供 Seedance API Base URL，请设置 SEEDANCE_API_BASE_URL")
    return SeedanceClient(api_key=api_key, base_url=resolved_base_url)


def _build_scene_prompt(
    scene: dict[str, Any],
    product: dict[str, Any],
    source_segment: dict[str, Any] | None,
    aspect_ratio: str,
    resolution: str,
    generation_profile: str,
    template_scene: dict[str, Any] | None = None,
    source_reference_frames: list[dict[str, Any]] | None = None,
) -> str:
    role = scene["role"]
    product_name = product["name"]
    visual_description = _product_visual_description(product)
    selling_point = scene.get("selling_point", "")
    subtitle = scene.get("subtitle_suggestion", "")
    source_hint = ""
    if source_segment and source_segment.get("ocr_texts"):
        source_hint = "；参考爆款片段字幕：" + " / ".join(source_segment["ocr_texts"][:3])

    scene_map = {
        "hook": "开头钩子镜头，先建立停留理由",
        "product_or_try_on": "展示鞋型、上脚比例和整体状态",
        "detail_or_selling_point": "展示材质、扣带、鞋头和细节卖点",
        "transition_or_scene": "补充通勤或日常场景感，镜头克制",
        "closing": "收束转化，给出明确购买理由",
    }
    scene_directive = scene_map.get(role, "围绕商品卖点完成短视频分镜")
    prompt_parts = [
        "生成一段适合抖音女鞋带货的短视频片段。",
        f"商品是{product_name}，视觉特征为{visual_description}。",
        f"分镜角色：{role}。",
        f"镜头目标：{scene_directive}。",
        f"主卖点：{selling_point or '舒适与穿搭适配'}。",
        f"字幕建议：{subtitle or '突出鞋型和卖点'}。",
        f"保持 9:16 竖版，成片分辨率目标 {resolution}，镜头时长要自然。",
        "商品主体必须稳定，不要改变鞋型、颜色、扣带数量、鞋头结构和材质光泽。",
    ]
    if source_hint:
        prompt_parts.append(source_hint)
    if source_reference_frames:
        prompt_parts.extend(_build_source_reference_prompt_parts(source_reference_frames))
    if template_scene:
        prompt_parts.extend(_build_template_prompt_parts(template_scene))
    if _uses_tryon_text_video(role, generation_profile):
        prompt_parts.extend(
            _build_tryon_prompt_parts(scene, product, source_segment, aspect_ratio, resolution)
        )
    if role == "hook":
        prompt_parts.append("画面开头 1 秒内必须把鞋子主体放在视觉中心。")
    if role == "detail_or_selling_point":
        prompt_parts.append("细节镜头要靠近鞋面、鞋头或扣带，不要做大幅变形运动。")
    if role == "closing":
        prompt_parts.append("结尾保留稳定停顿，方便后期叠加转化文案。")
    prompt_parts.append(f"输出应适合后续与其它片段拼接成 {aspect_ratio} 成片。")
    return " ".join(prompt_parts)


def _build_negative_prompt(
    scene: dict[str, Any],
    product: dict[str, Any],
    template_scene: dict[str, Any] | None = None,
) -> str:
    attributes = product.get("attributes", {})
    detail_features = "、".join(product.get("detail_features", []))
    selling_point = scene.get("selling_point", "")
    role = scene.get("role", "")
    parts = [
        "不要出现额外鞋带、额外扣带、错误的鞋跟高度、错误的鞋头形状、错误的材质纹理、"
        "错误的品牌字样、人物肢体畸变、鞋子数量变化、左右脚结构不一致、低清晰度、强闪烁、"
        "夸张镜头拉伸、字幕乱码、背景喧宾夺主。",
        f"必须保持颜色为{_map_color(attributes.get('color', ''))}。",
        f"闭合方式必须是{_map_closure(attributes.get('closure', ''))}。",
        f"鞋头必须是{_map_toe_shape(attributes.get('toe_shape', ''))}。",
        f"材质观感必须是{_map_material(attributes.get('material', ''))}。",
    ]
    if detail_features:
        parts.append(f"细节必须保留：{detail_features}。")
    if selling_point:
        parts.append(f"当前分镜卖点：{selling_point}。")
    if role in TRYON_ROLES:
        parts.append(
            "不要生成白底商品图、孤立鞋子、鞋面局部动画、没有脚的鞋、手拿鞋、桌面摆拍、"
            "鞋盒展示、空镜、赤脚、袜子代替鞋、运动鞋、拖鞋、儿童或男性模特。"
        )
    if template_scene:
        not_acceptable = "、".join(template_scene.get("not_acceptable", []))
        if not_acceptable:
            parts.append(f"按爆款模板适配的不可接受项：{not_acceptable}。")
    return "".join(parts)


def _build_request_payload(
    model: str,
    prompt: str,
    negative_prompt: str,
    reference_images: list[dict[str, Any]],
    duration_seconds: float,
    aspect_ratio: str,
    resolution: str,
    watermark: bool,
    generation_mode: str,
    source_reference_frames: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _validate_video_generation_model(model)
    source_reference_frames = source_reference_frames or []
    if not reference_images:
        raise ValueError("视频生成至少需要 1 张商品参考图。")

    if not _uses_first_frame(generation_mode):
        ordered_reference_images = _build_ordered_reference_images(
            product_images=reference_images,
            source_reference_frames=source_reference_frames,
        )
        reference_instruction = _build_reference_payload_instruction(ordered_reference_images)
        prompt_text = (
            f"{prompt}\n"
            f"{reference_instruction}\n"
            f"负向约束：{negative_prompt}\n"
            f"时长：{max(1, int(round(duration_seconds)))} 秒。\n"
            f"画幅：{aspect_ratio}。\n"
            f"分辨率：{resolution}。\n"
            f"水印：{'保留' if watermark else '关闭'}。"
        )
        return {
            "model": model,
            "content": [
                {
                    "type": "text",
                    "text": prompt_text,
                },
                *_build_reference_image_content(ordered_reference_images, "reference_image"),
            ],
            "ratio": aspect_ratio,
            "duration": max(1, int(round(duration_seconds))),
            "resolution": resolution,
            "watermark": watermark,
        }

    first_image = reference_images[0]
    first_frame_url = first_image.get("public_url") or _build_data_url(first_image["local_path"])
    reference_instruction = (
        "随请求附加了 1 张 first_frame 商品首帧；目标鞋款必须严格以该首帧商品图为准。"
    )
    prompt_text = (
        f"{prompt}\n"
        f"{reference_instruction}\n"
        f"负向约束：{negative_prompt}\n"
        f"时长：{max(1, int(round(duration_seconds)))} 秒。\n"
        f"画幅：{aspect_ratio}。\n"
        f"分辨率：{resolution}。\n"
        f"水印：{'保留' if watermark else '关闭'}。"
    )
    return {
        "model": model,
        "content": [
            {
                "type": "text",
                "text": prompt_text,
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": first_frame_url,
                },
                "role": "first_frame",
            },
        ],
        "ratio": aspect_ratio,
        "duration": max(1, int(round(duration_seconds))),
        "resolution": resolution,
        "watermark": watermark,
    }


def _product_visual_description(product: dict[str, Any]) -> str:
    attributes = product.get("attributes", {})
    parts = [
        _map_color(attributes.get("color", "")),
        _map_material(attributes.get("material", "")),
        _map_toe_shape(attributes.get("toe_shape", "")),
        _map_closure(attributes.get("closure", "")),
    ]
    detail_features = "、".join(product.get("detail_features", []))
    if detail_features:
        parts.append(detail_features)
    return "，".join(part for part in parts if part)


def _build_reference_image_content(
    images: list[dict[str, Any]],
    role: str,
) -> list[dict[str, Any]]:
    content = []
    for image in images:
        image_url = image.get("public_url") or _build_data_url(image["local_path"])
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_url,
                },
                "role": role,
            }
        )
    return content


def _build_ordered_reference_images(
    product_images: list[dict[str, Any]],
    source_reference_frames: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    product_refs = [
        {**image, "reference_purpose": "product"}
        for image in product_images[:MAX_PRODUCT_REFERENCE_IMAGES]
    ]
    hot_frame_limit = max(0, MAX_REFERENCE_IMAGE_CONTENT - len(product_refs))
    hot_refs = [
        {**frame, "reference_purpose": "hot_video_structure"}
        for frame in source_reference_frames[:hot_frame_limit]
    ]
    return [*product_refs, *hot_refs]


def _build_reference_image_order(
    product_images: list[dict[str, Any]],
    source_reference_frames: list[dict[str, Any]],
    generation_mode: str,
) -> list[dict[str, Any]]:
    if _uses_first_frame(generation_mode):
        first_image = product_images[0] if product_images else {}
        return [
            {
                "position": 1,
                "api_role": "first_frame",
                "purpose": "product",
                "local_path": first_image.get("local_path", ""),
            }
        ]

    order = []
    for index, image in enumerate(
        _build_ordered_reference_images(product_images, source_reference_frames),
        start=1,
    ):
        order.append(
            {
                "position": index,
                "api_role": "reference_image",
                "purpose": image.get("reference_purpose", ""),
                "local_path": image.get("local_path", ""),
            }
        )
    return order


def _build_reference_payload_instruction(ordered_reference_images: list[dict[str, Any]]) -> str:
    product_count = sum(
        1 for image in ordered_reference_images if image.get("reference_purpose") == "product"
    )
    hot_count = sum(
        1
        for image in ordered_reference_images
        if image.get("reference_purpose") == "hot_video_structure"
    )
    parts = [
        f"随请求附加了 {len(ordered_reference_images)} 张 reference_image。"
        f"其中前 {product_count} 张是商品参考图，目标鞋款必须严格以这些商品图为准，"
        "不能自行改款。"
    ]
    if hot_count:
        parts.append(
            f"后 {hot_count} 张是爆款源分镜帧，只用于学习构图、机位、动作节奏和人物露出范围，"
            "不能照搬源视频鞋款。"
        )
    return " ".join(parts)


def _generation_mode(role: str, generation_profile: str) -> str:
    if _uses_tryon_text_video(role, generation_profile):
        return "text_to_video_model_tryon"
    if role in {"hook", "detail_or_selling_point", "closing"}:
        return "image_to_video_preserve_product"
    if role == "product_or_try_on":
        return "image_to_video_low_risk_showcase"
    return "image_to_video_cautious_scene"


def _risk_level(role: str, generation_profile: str) -> str:
    if _uses_tryon_text_video(role, generation_profile):
        return "medium"
    if role == "transition_or_scene":
        return "high"
    if role == "product_or_try_on":
        return "medium"
    return "low"


def _submit_recommended(role: str, generation_profile: str) -> bool:
    if _uses_tryon_text_video(role, generation_profile):
        return True
    return role != "transition_or_scene"


def _index_template_adaptations(
    template_adaptation: dict[str, Any] | None,
) -> dict[int, dict[str, Any]]:
    if not template_adaptation:
        return {}
    indexed = {}
    for scene in template_adaptation.get("scene_adaptations", []):
        scene_index = scene.get("scene_index")
        if isinstance(scene_index, int):
            indexed[scene_index] = scene
    return indexed


def _compact_template_adaptation(template_scene: dict[str, Any] | None) -> dict[str, Any]:
    if not template_scene:
        return {}
    must_follow = template_scene.get("must_follow_template", {})
    return {
        "source_template_scene_id": template_scene.get("source_template_scene_id", ""),
        "target_visual": template_scene.get("target_visual", ""),
        "visual_type": must_follow.get("visual_type", ""),
        "framing": must_follow.get("framing", ""),
        "action": must_follow.get("action", ""),
        "quality_checks": template_scene.get("quality_checks", []),
    }


def _build_template_prompt_parts(template_scene: dict[str, Any]) -> list[str]:
    must_follow = template_scene.get("must_follow_template", {})
    parts = [
        "以下是从爆款源视频提炼出的可复用镜头模板，必须优先遵循。",
        f"模板画面类型：{must_follow.get('visual_type', '')}。",
        f"模板构图：{must_follow.get('framing', '')}。",
        f"模板角度：{must_follow.get('camera_angle', '')}。",
        f"模板运镜：{must_follow.get('camera_motion', '')}。",
        f"模板动作：{must_follow.get('action', '')}。",
        f"模特可见性：{must_follow.get('model_visibility', '')}。",
        f"商品可见性：{must_follow.get('product_visibility', '')}。",
        f"目标画面：{template_scene.get('target_visual', '')}。",
    ]
    for label, key in (
        ("模板固定项", "fixed_parts"),
        ("目标商品必保留特征", "must_keep_product_features"),
        ("可变化项", "acceptable_variation"),
        ("质量检查", "quality_checks"),
        ("不可接受项", "not_acceptable"),
    ):
        values = template_scene.get(key) or must_follow.get(key) or []
        if values:
            parts.append(f"{label}：{'、'.join(str(value) for value in values)}。")
    parts.append("如果无法同时满足模板构图和商品一致性，优先保证鞋真实穿在脚上和鞋款结构正确。")
    return parts


def _build_source_reference_prompt_parts(
    source_reference_frames: list[dict[str, Any]],
) -> list[str]:
    labels = "、".join(
        frame.get("label", "") for frame in source_reference_frames if frame.get("label")
    )
    return [
        "请求中已附加爆款源视频当前分镜的关键帧，必须把这些图只当作镜头结构参考。",
        f"源分镜关键帧数量：{len(source_reference_frames)}，位置：{labels or '未标注'}。",
        "源分镜关键帧用于约束构图、机位、人物露出范围、动作节奏和生活化场景。",
        "源分镜里的原鞋款和字幕不要照搬；目标商品外观必须以商品参考图为准。",
    ]


def _resolve_source_reference_frames(
    source_segment: dict[str, Any] | None,
    analysis_dir: Path | None,
) -> list[dict[str, Any]]:
    if not source_segment or analysis_dir is None:
        return []

    frames = []
    for frame in source_segment.get("review_frames", []):
        image_path = frame.get("image_path", "")
        if not image_path:
            continue
        path = _resolve_analysis_asset_path(analysis_dir, image_path)
        if not path.exists():
            continue
        frames.append(
            {
                "label": frame.get("label", ""),
                "timestamp_seconds": frame.get("timestamp_seconds"),
                "local_path": str(path),
                "source": "hot_video_segment_frame",
            }
        )

    if frames:
        return frames

    cover_frame = source_segment.get("cover_frame", "")
    if cover_frame:
        path = _resolve_analysis_asset_path(analysis_dir, cover_frame)
        if path.exists():
            return [
                {
                    "label": "cover",
                    "timestamp_seconds": source_segment.get("start"),
                    "local_path": str(path),
                    "source": "hot_video_cover_frame",
                }
            ]
    return []


def _resolve_analysis_asset_path(analysis_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return analysis_dir / path


def _validate_generation_profile(generation_profile: str) -> None:
    valid_profiles = {GENERATION_PROFILE_PRODUCT, GENERATION_PROFILE_TRYON}
    if generation_profile not in valid_profiles:
        raise ValueError(
            f"未知的 Seedance 生成画像：{generation_profile}。"
            f"可选值：{', '.join(sorted(valid_profiles))}"
        )


def _uses_tryon_text_video(role: str, generation_profile: str) -> bool:
    return generation_profile == GENERATION_PROFILE_TRYON and role in TRYON_ROLES


def _uses_first_frame(generation_mode: str) -> bool:
    return generation_mode.startswith("image_to_video")


def _build_tryon_prompt_parts(
    scene: dict[str, Any],
    product: dict[str, Any],
    source_segment: dict[str, Any] | None,
    aspect_ratio: str,
    resolution: str,
) -> list[str]:
    role = scene["role"]
    source_index = scene.get("source_segment_index") or (
        source_segment.get("index") if source_segment else ""
    )
    product_name = product["name"]
    visual_description = _product_visual_description(product)
    scene_instruction = _tryon_scene_instruction(role, source_index)
    product_details = "、".join(product.get("detail_features", [])) or "鞋型、扣带和鞋头细节"

    return [
        "当前分镜必须是真人模特上脚试穿镜头，不是商品静物图动画。",
        "画面中必须出现一位成年女性模特，鞋必须真实穿在模特脚上。",
        "双脚或至少一只完整穿鞋的脚必须清楚可见，脚踝、小腿和鞋口关系要自然连续。",
        f"模特脚上必须穿着{product_name}，鞋子是{visual_description}。",
        f"必须保留商品关键细节：{product_details}。",
        "鞋子必须踩在真实地面或室内场景中，不能漂浮、不能悬空、不能只出现孤立鞋面。",
        "镜头主体优先是模特脚部、小腿和穿搭下半身，鞋在画面下半部保持清晰可辨。",
        "动作要自然：走路、抬脚、轻微转身、停步展示、扣带整理，符合女鞋电商短视频。",
        "参考爆款视频的生活方式试穿结构：竖屏手机感、节奏快、镜头贴近脚部和穿搭。",
        "画面必须像真实手机拍摄的女鞋试穿短视频，不要像电商白底详情页或产品渲染图。",
        (
            f"本段参考源片段序号：{source_index or '未指定'}，"
            f"画幅保持 {aspect_ratio}，目标 {resolution}。"
        ),
        scene_instruction,
        "不要让商品漂浮在空中，不要只做鞋面局部变形，不要生成纯白底商品详情页。",
        "不要只出现手拿鞋、鞋盒、桌面摆拍、空镜、鞋子特写动画或没有脚的商品展示。",
        "不要出现儿童、男性模特、赤脚、拖鞋、运动鞋或与参考商品不一致的鞋款。",
    ]


def _tryon_scene_instruction(role: str, source_index: Any) -> str:
    if role == "hook":
        return (
            "开头 1 秒内用模特穿鞋走入画面制造停留，先给脚部和鞋的低机位近景，"
            "再轻微上移到下半身穿搭。"
        )
    if role == "product_or_try_on":
        return (
            "使用低机位脚部近景，模特连续走两到三步，重点表现上脚比例、鞋型、"
            "双带扣带和走路状态。"
        )
    if role == "detail_or_selling_point":
        return (
            "使用穿在脚上的细节近景，镜头贴近鞋头雕花、双带扣带和亮面皮革，"
            "脚可以轻微转动但不能变成静物商品图。"
        )
    if role == "closing":
        return (
            "结尾用模特穿鞋停步定格，双脚自然站立，鞋子清楚可见，画面留出字幕和转化文案空间。"
        )
    if source_index in {4, "4"}:
        return "表现穿脱或扣带整理动作，手部可以短暂入镜，但鞋必须已经穿在脚上。"
    if source_index in {5, "5"}:
        return "表现通勤或日常走动，模特连续走几步，突出久走舒适和百搭。"
    if source_index in {6, "6"}:
        return "表现坐下或停步时的侧面鞋型，突出柔软、轻便和不易变形。"
    if source_index in {7, "7"}:
        return "做一个简短转场动作，脚步经过镜头或轻微转身，方便后续拼接。"
    return "用模特真实上脚的生活化镜头完成该分镜。"


def _merge_public_urls(
    reference_images: list[dict[str, Any]],
    public_urls: list[str],
) -> list[dict[str, Any]]:
    merged = []
    for index, image in enumerate(reference_images):
        public_url = public_urls[index] if index < len(public_urls) else ""
        merged.append({**image, "public_url": public_url})
    return merged


def _ensure_image_urls(payload: dict[str, Any]) -> None:
    missing = []
    for item in payload.get("content", []):
        if item.get("type") != "image_url":
            continue
        image_url = item.get("image_url", {})
        url = image_url.get("url", "") if isinstance(image_url, dict) else ""
        if not url:
            missing.append(url or "<EMPTY_URL>")
    if missing:
        raise ValueError("提交 Seedance 任务前缺少可访问的商品图 URL")


def _extract_task_id(response: dict[str, Any]) -> str:
    for key in ("id", "task_id"):
        if response.get(key):
            return str(response[key])
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("id", "task_id"):
            if data.get(key):
                return str(data[key])
    return ""


def _extract_task_status(response: dict[str, Any]) -> str:
    for key in ("status", "state", "task_status"):
        if response.get(key):
            return str(response[key])
    data = response.get("data")
    if isinstance(data, dict):
        for key in ("status", "state", "task_status"):
            if data.get(key):
                return str(data[key])
    return ""


def _normalize_tasks_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith(TASKS_PATH):
        return base
    if base.endswith("/api/v3") or base.endswith("/api/v1"):
        return f"{base}/contents/generations/tasks"
    return f"{base}{TASKS_PATH}"


def _validate_video_generation_model(model: str) -> None:
    lowered = model.lower()
    if lowered.startswith("doubao-seed-2-0-"):
        raise ValueError(
            "当前配置的模型是 Doubao Seed 2.0 多模态理解模型，不是视频生成模型。"
            "视频生成请改用 Seedance 视频模型，例如 doubao-seedance-1-0-pro-250528。"
        )


def _resolve_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return project_path(path_value)


def _build_data_url(path_value: str) -> str:
    path = _resolve_path(path_value)
    mime_type = _guess_mime_type(path)
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _guess_mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _map_color(value: str) -> str:
    mapping = {
        "black": "黑色",
        "burgundy": "酒红色",
    }
    return mapping.get(value, value or "深色")


def _map_material(value: str) -> str:
    mapping = {
        "soft_microfiber": "柔软超纤材质",
        "patent_leather": "漆皮质感",
        "glossy_leather": "带光泽的皮面质感",
    }
    return mapping.get(value, value or "皮面材质")


def _map_closure(value: str) -> str:
    mapping = {
        "slip_on": "一脚蹬",
        "buckle_strap": "单扣带",
        "double_buckle_strap": "双扣带",
    }
    return mapping.get(value, value or "鞋面闭合结构")


def _map_toe_shape(value: str) -> str:
    mapping = {
        "round": "圆头",
        "square_round": "方圆头",
    }
    return mapping.get(value, value or "鞋头结构")
