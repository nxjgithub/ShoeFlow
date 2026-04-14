"""Seedance 片段质量审核清单。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gemeiqi.repository import dump_json
from gemeiqi.seedance import scene_batch_label


def build_generation_quality_review(
    plan: dict[str, Any],
    tasks: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """根据生成计划和任务状态生成可人工勾选的质量审核表。"""

    tasks_by_scene = _index_tasks(tasks or {})
    scenes = []
    for segment in plan.get("segments", []):
        scene_index = segment["scene_index"]
        task = tasks_by_scene.get(scene_index, {})
        template_checks = segment.get("template_adaptation", {}).get("quality_checks", [])
        product_checks = _product_consistency_checks(segment)
        template_fidelity_checks = _template_fidelity_checks(segment, template_checks)
        technical_checks = _technical_delivery_checks(segment)
        scenes.append(
            {
                "scene_index": scene_index,
                "role": segment["role"],
                "generation_mode": segment.get("generation_mode", ""),
                "reference_strategy": segment.get("reference_strategy", ""),
                "submission_batch": scene_batch_label(plan, scene_index),
                "stability_tier": segment.get("stability_tier", ""),
                "task_id": task.get("task_id", ""),
                "task_status": task.get("latest_status") or task.get("status", "not_submitted"),
                "source_template": segment.get("template_adaptation", {}),
                "required_checks": _required_checks(
                    product_checks,
                    template_fidelity_checks,
                    technical_checks,
                ),
                "review_dimensions": {
                    "product_consistency": _to_check_items(product_checks),
                    "template_fidelity": _to_check_items(template_fidelity_checks),
                    "technical_delivery": _to_check_items(technical_checks),
                },
                "auto_reject_if_any": _auto_reject_rules(segment),
                "review_result": {
                    "approved_for_final": False,
                    "needs_regeneration": True,
                    "failure_reasons": [],
                    "human_notes": "",
                },
                "retry_hint": _retry_hint(segment),
            }
        )

    return {
        "id": f"quality_review_{plan.get('id', 'seedance_plan')}",
        "plan_id": plan.get("id", ""),
        "product_id": plan.get("product_id", ""),
        "template_adaptation_id": plan.get("template_adaptation_id", ""),
        "status": "pending_human_review",
        "scenes": scenes,
        "trace": {
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": "gemeiqi.quality_review.build_generation_quality_review",
        },
    }


def write_quality_review(path: Path, review: dict[str, Any]) -> None:
    """写出质量审核 JSON。"""

    dump_json(path, review)


def _index_tasks(tasks: dict[str, Any]) -> dict[int, dict[str, Any]]:
    indexed = {}
    for task in tasks.get("tasks", []):
        scene_index = task.get("scene_index")
        if isinstance(scene_index, int):
            indexed[scene_index] = task
    return indexed


def _required_checks(*check_groups: list[str]) -> list[dict[str, Any]]:
    merged = []
    seen = set()
    for group in check_groups:
        for text in group:
            if text in seen:
                continue
            seen.add(text)
            merged.append({"check": text, "passed": False, "notes": ""})
    return merged


def _to_check_items(checks: list[str]) -> list[dict[str, Any]]:
    return [{"check": text, "passed": False, "notes": ""} for text in checks]


def _product_consistency_checks(segment: dict[str, Any]) -> list[str]:
    checks = [
        "是否出现成年女性模特",
        "鞋是否真实穿在脚上",
        "是否没有白底商品图或孤立鞋子",
        "目标商品颜色、鞋头、扣带和材质是否正确",
    ]
    if segment.get("reference_strategy") == "product_and_hot_video_reference_images":
        checks.append("商品图优先级是否高于爆款源帧，是否没有被源视频鞋款带偏")
    return checks


def _template_fidelity_checks(segment: dict[str, Any], template_checks: list[str]) -> list[str]:
    checks = [
        "是否符合源模板构图和动作",
        "是否保留了爆款分镜中的人物露出范围和机位关系",
    ]
    if segment.get("generation_mode") == "image_to_video_model_tryon_first_frame":
        checks.append("首帧过渡是否被裁干净，是否没有明显从静物图变成上脚图的过程")
    merged = []
    seen = set()
    for text in [*checks, *template_checks]:
        if text in seen:
            continue
        seen.add(text)
        merged.append(text)
    return merged


def _technical_delivery_checks(segment: dict[str, Any]) -> list[str]:
    checks = [
        "画面是否稳定，没有明显抖动、拉伸或结构漂移",
        "鞋头、扣带、左右脚是否前后连续一致",
    ]
    if segment.get("generation_mode") == "reference_to_video_model_tryon":
        checks.append("多参考图约束是否生效，镜头风格来自爆款分镜而不是替换成别的鞋款")
    return checks


def _auto_reject_rules(segment: dict[str, Any]) -> list[str]:
    rules = [
        "出现非目标鞋款或关键结构错误",
        "没有模特上脚，或鞋没有穿在脚上",
        "出现白底静物商品图并直接进入成片",
        "左右脚结构、扣带数量、鞋头轮廓前后不一致",
    ]
    if segment.get("generation_mode") == "reference_to_video_model_tryon":
        rules.append("爆款源帧主导了鞋款，导致商品被替换成近似款")
    return rules


def _retry_hint(segment: dict[str, Any]) -> str:
    adaptation = segment.get("template_adaptation", {})
    visual_type = adaptation.get("visual_type") or segment.get("role", "")
    framing = adaptation.get("framing", "")
    action = adaptation.get("action", "")
    return (
        f"重跑时保持 visual_type={visual_type}，构图={framing}，动作={action}。"
        "只重跑该分镜，不要全量重跑。"
    )
