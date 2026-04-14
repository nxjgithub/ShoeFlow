"""项目早期样例数据使用的轻量数据契约校验。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

SUPPORTED_PLATFORMS = {"douyin", "xiaohongshu", "taobao"}
SUPPORTED_CATEGORIES = {"women_shoes"}


@dataclass(frozen=True)
class ValidationIssue:
    """业务对象中的单个校验问题。"""

    object_id: str
    field: str
    message: str

    def format(self) -> str:
        return f"{self.object_id}: {self.field} - {self.message}"


REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "video_sample": (
        "id",
        "platform",
        "title",
        "source_type",
        "source",
        "category",
        "metrics",
        "tags",
    ),
    "product": (
        "id",
        "name",
        "category",
        "shoe_type",
        "attributes",
        "primary_selling_points",
        "secondary_selling_points",
        "target_audience",
        "target_scenarios",
        "risk_notes",
        "asset_refs",
    ),
    "template": (
        "id",
        "name",
        "version",
        "source_analysis_ids",
        "platforms",
        "hook_type",
        "scene_structure",
        "selling_point_order",
        "copywriting_style",
        "product_variables",
    ),
    "performance_record": (
        "id",
        "script_id",
        "platform",
        "published_at",
        "metrics",
        "quality_review",
        "notes",
    ),
    "script_output": (
        "id",
        "template_id",
        "product_id",
        "platform",
        "title_options",
        "scenes",
        "material_checklist",
        "trace",
    ),
    "video_analysis": (
        "id",
        "sample_id",
        "source_video",
        "summary",
        "hook_type",
        "primary_selling_points",
        "segments",
        "trace",
    ),
}


def validate_collection(kind: str, records: Iterable[Mapping[str, Any]]) -> list[ValidationIssue]:
    """按指定轻量契约校验一组字典对象。"""

    issues: list[ValidationIssue] = []
    required = REQUIRED_FIELDS[kind]

    for index, record in enumerate(records):
        object_id = str(record.get("id") or f"{kind}[{index}]")
        for field in required:
            if field not in record:
                issues.append(ValidationIssue(object_id, field, "缺少必填字段"))

        platform = record.get("platform")
        if platform is not None and platform not in SUPPORTED_PLATFORMS:
            issues.append(
                ValidationIssue(object_id, "platform", f"不支持的平台 {platform!r}")
            )

        category = record.get("category")
        if category is not None and category not in SUPPORTED_CATEGORIES:
            issues.append(
                ValidationIssue(object_id, "category", f"不支持的品类 {category!r}")
            )

        if kind == "template":
            issues.extend(_validate_template(object_id, record))
        elif kind == "product":
            issues.extend(_validate_product(object_id, record))
        elif kind == "video_analysis":
            issues.extend(_validate_video_analysis(object_id, record))

    return issues


def require_no_issues(kind: str, records: Iterable[Mapping[str, Any]]) -> None:
    """如果契约校验发现问题，则抛出 ValueError。"""

    issues = validate_collection(kind, records)
    if issues:
        formatted = "\n".join(issue.format() for issue in issues)
        raise ValueError(f"{kind} 校验失败：\n{formatted}")


def _validate_template(object_id: str, record: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    platforms = record.get("platforms")
    if not isinstance(platforms, list) or not platforms:
        issues.append(ValidationIssue(object_id, "platforms", "必须是非空列表"))
    elif unsupported := [item for item in platforms if item not in SUPPORTED_PLATFORMS]:
        issues.append(
            ValidationIssue(
                object_id,
                "platforms",
                f"包含不支持的平台：{unsupported}",
            )
        )

    scene_structure = record.get("scene_structure")
    if not isinstance(scene_structure, list) or not scene_structure:
        issues.append(ValidationIssue(object_id, "scene_structure", "必须是非空列表"))

    return issues


def _validate_product(object_id: str, record: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for field in ("primary_selling_points", "target_audience", "target_scenarios"):
        value = record.get(field)
        if not isinstance(value, list) or not value:
            issues.append(ValidationIssue(object_id, field, "必须是非空列表"))

    attributes = record.get("attributes")
    if not isinstance(attributes, dict) or not attributes:
        issues.append(ValidationIssue(object_id, "attributes", "必须是非空对象"))

    return issues


def _validate_video_analysis(object_id: str, record: Mapping[str, Any]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    segments = record.get("segments")
    if not isinstance(segments, list) or not segments:
        return [ValidationIssue(object_id, "segments", "必须是非空列表")]

    required_segment_fields = (
        "index",
        "start",
        "end",
        "role",
        "visual_focus",
        "selling_point",
        "copywriting",
        "reusable",
        "review_status",
    )
    for segment_index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            issues.append(
                ValidationIssue(
                    object_id,
                    f"segments[{segment_index}]",
                    "片段必须是对象",
                )
            )
            continue

        for field in required_segment_fields:
            if field not in segment:
                issues.append(
                    ValidationIssue(
                        object_id,
                        f"segments[{segment_index}].{field}",
                        "缺少必填字段",
                    )
                )

        start = segment.get("start")
        end = segment.get("end")
        if isinstance(start, int | float) and isinstance(end, int | float) and end <= start:
            issues.append(
                ValidationIssue(
                    object_id,
                    f"segments[{segment_index}].end",
                    "结束时间必须大于开始时间",
                )
            )

    return issues
