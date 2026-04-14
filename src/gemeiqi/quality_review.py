"""Seedance 片段质量审核清单。"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gemeiqi.repository import dump_json


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
        scenes.append(
            {
                "scene_index": scene_index,
                "role": segment["role"],
                "generation_mode": segment.get("generation_mode", ""),
                "task_id": task.get("task_id", ""),
                "task_status": task.get("latest_status") or task.get("status", "not_submitted"),
                "source_template": segment.get("template_adaptation", {}),
                "required_checks": _required_checks(template_checks),
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


def _required_checks(template_checks: list[str]) -> list[dict[str, Any]]:
    base_checks = [
        "是否出现成年女性模特",
        "鞋是否真实穿在脚上",
        "是否没有白底商品图或孤立鞋子",
        "目标商品颜色、鞋头、扣带和材质是否正确",
        "是否符合源模板构图和动作",
    ]
    merged = []
    seen = set()
    for text in [*base_checks, *template_checks]:
        if text in seen:
            continue
        seen.add(text)
        merged.append({"check": text, "passed": False, "notes": ""})
    return merged


def _retry_hint(segment: dict[str, Any]) -> str:
    adaptation = segment.get("template_adaptation", {})
    visual_type = adaptation.get("visual_type") or segment.get("role", "")
    framing = adaptation.get("framing", "")
    action = adaptation.get("action", "")
    return (
        f"重跑时保持 visual_type={visual_type}，构图={framing}，动作={action}。"
        "只重跑该分镜，不要全量重跑。"
    )
