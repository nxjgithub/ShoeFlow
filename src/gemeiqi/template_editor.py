"""模板 Markdown 编辑卡的导出与回写。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write_template_editor_markdown(path: Path, template: dict[str, Any]) -> None:
    """把模板对象导出为更适合人工修改的 Markdown 编辑卡。"""

    copywriting_style = template.get("copywriting_style", {})
    scene_lines = [
        "| source_segment_index | role | duration_seconds | goal | reusable_hint | ocr_examples |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for scene in template.get("scene_structure", []):
        scene_lines.append(
            "| "
            f"{scene.get('source_segment_index', '')} | "
            f"{scene.get('role', '')} | "
            f"{scene.get('duration_seconds', '')} | "
            f"{scene.get('goal', '')} | "
            f"{scene.get('reusable_hint', '')} | "
            f"{' <br> '.join(scene.get('ocr_examples', []))} |"
        )

    lines = [
        "# 模板编辑卡",
        "",
        "请优先修改这个文件，再通过命令把它回写成 JSON 模板。",
        "",
        "## 基础信息",
        "",
        f"- id: {template.get('id', '')}",
        f"- name: {template.get('name', '')}",
        f"- version: {template.get('version', '')}",
        f"- platforms: {', '.join(template.get('platforms', []))}",
        f"- hook_type: {template.get('hook_type', '')}",
        f"- source_analysis_ids: {', '.join(template.get('source_analysis_ids', []))}",
        f"- review_status: {template.get('review_status', '')}",
        "",
        "## 模板摘要",
        "",
        template.get("template_summary", ""),
        "",
        "## 卖点顺序",
        "",
    ]
    lines.extend(f"- {item}" for item in template.get("selling_point_order", []))
    lines.extend(
        [
            "",
            "## 商品变量位",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in template.get("product_variables", []))
    lines.extend(
        [
            "",
            "## 复用说明",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in template.get("reuse_notes", []))
    lines.extend(
        [
            "",
            "## 文案风格",
            "",
            f"- tone: {copywriting_style.get('tone', '')}",
            f"- pace: {copywriting_style.get('pace', '')}",
            f"- keywords: {' | '.join(copywriting_style.get('keywords', []))}",
            "",
            "## 片段结构",
            "",
        ]
    )
    lines.extend(scene_lines)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_template_from_markdown(path: Path) -> dict[str, Any]:
    """从 Markdown 编辑卡回写模板对象。"""

    lines = path.read_text(encoding="utf-8").splitlines()
    sections = _split_sections(lines)

    base = _parse_key_value_bullets(sections.get("基础信息", []))
    style = _parse_key_value_bullets(sections.get("文案风格", []))
    template_summary = "\n".join(sections.get("模板摘要", [])).strip()
    selling_point_order = _parse_bullets(sections.get("卖点顺序", []))
    product_variables = _parse_bullets(sections.get("商品变量位", []))
    reuse_notes = _parse_bullets(sections.get("复用说明", []))
    scene_structure = _parse_scene_table(sections.get("片段结构", []))

    keywords = style.get("keywords", "")
    return {
        "id": base.get("id", ""),
        "name": base.get("name", ""),
        "version": base.get("version", ""),
        "source_analysis_ids": _split_csv(base.get("source_analysis_ids", "")),
        "platforms": _split_csv(base.get("platforms", "")),
        "hook_type": base.get("hook_type", ""),
        "scene_structure": scene_structure,
        "selling_point_order": selling_point_order,
        "copywriting_style": {
            "tone": style.get("tone", ""),
            "pace": style.get("pace", ""),
            "keywords": [item for item in keywords.split("|") if item.strip()],
        },
        "product_variables": product_variables,
        "template_summary": template_summary,
        "reuse_notes": reuse_notes,
        "review_status": base.get("review_status", ""),
    }


def _split_sections(lines: list[str]) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("## "):
            current = line.removeprefix("## ").strip()
            sections[current] = []
            continue
        if not current:
            continue
        sections[current].append(line)
    return sections


def _parse_bullets(lines: list[str]) -> list[str]:
    items = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _parse_key_value_bullets(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in _parse_bullets(lines):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _parse_scene_table(lines: list[str]) -> list[dict[str, Any]]:
    rows = [line for line in lines if line.strip().startswith("|")]
    if len(rows) < 3:
        return []

    headers = [cell.strip() for cell in rows[0].strip().strip("|").split("|")]
    scenes = []
    for row in rows[2:]:
        values = [cell.strip() for cell in row.strip().strip("|").split("|")]
        if len(values) != len(headers):
            continue
        item = dict(zip(headers, values, strict=False))
        source_segment_index = item.get("source_segment_index", "")
        duration_seconds = item.get("duration_seconds", "")
        scenes.append(
            {
                "source_segment_index": int(source_segment_index) if source_segment_index else None,
                "role": item.get("role", ""),
                "duration_seconds": float(duration_seconds) if duration_seconds else 0.0,
                "goal": item.get("goal", ""),
                "reusable_hint": item.get("reusable_hint", ""),
                "ocr_examples": [
                    part.strip()
                    for part in item.get("ocr_examples", "").split("<br>")
                    if part.strip()
                ],
            }
        )
    return scenes


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]
