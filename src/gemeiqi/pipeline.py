"""项目初始骨架中的最小可替换业务管线。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def score_template_for_product(
    template: dict[str, Any],
    product: dict[str, Any],
    platform: str,
) -> dict[str, Any]:
    """返回可解释的模板与商品适配结果。"""

    score = 0.2
    matched_reasons: list[str] = []
    warnings: list[str] = []

    if platform in template.get("platforms", []):
        score += 0.25
        matched_reasons.append(f"模板支持 {platform} 平台")
    else:
        warnings.append(f"模板未声明支持 {platform} 平台")

    product_points = set(product.get("primary_selling_points", []))
    template_points = set(template.get("selling_point_order", []))
    overlap = product_points.intersection(template_points)
    if overlap:
        score += min(0.3, 0.1 * len(overlap))
        matched_reasons.append("商品主卖点与模板卖点顺序存在重合")

    scenarios = product.get("target_scenarios", [])
    if any("通勤" in scenario or "上班" in scenario for scenario in scenarios):
        score += 0.15
        matched_reasons.append("商品目标场景适合通勤型内容结构")

    risk_notes = product.get("risk_notes", [])
    if risk_notes:
        warnings.extend(risk_notes)

    return {
        "id": f"match_{uuid4().hex[:12]}",
        "template_id": template["id"],
        "product_id": product["id"],
        "score": round(min(score, 1.0), 2),
        "matched_reasons": matched_reasons,
        "warnings": warnings,
        "variable_mapping": {
            "shoe_type": product.get("shoe_type"),
            "primary_selling_points": product.get("primary_selling_points", []),
            "target_scenarios": product.get("target_scenarios", []),
            "material": product.get("attributes", {}).get("material"),
            "heel_height_cm": product.get("attributes", {}).get("heel_height_cm"),
        },
    }


def build_script_output(
    product: dict[str, Any],
    template: dict[str, Any],
    match: dict[str, Any],
    platform: str = "douyin",
) -> dict[str, Any]:
    """根据商品和内容模板生成第一版脚本输出。"""

    product_points = product.get("primary_selling_points", [])
    title_options = [
        f"{product['name']}，通勤久走也要好看",
        f"这双{product['name']}适合每天出门穿",
        f"{product['name']}：把{_join_cn(product_points)}讲清楚",
    ]

    scenes = []
    for index, scene in enumerate(template.get("scene_structure", []), start=1):
        role = scene.get("role", f"scene_{index}")
        selling_point = _resolve_scene_selling_point(scene, template, index)
        shot_type = _infer_shot_type(role)
        production_mode = _infer_production_mode(role, product)
        subtitle_suggestion = _subtitle_suggestion(role, product, selling_point, platform)
        narration_suggestion = _narration_suggestion(role, product, selling_point, platform)
        scenes.append(
            {
                "index": index,
                "role": role,
                "duration_seconds": scene.get("duration_seconds"),
                "goal": scene.get("goal"),
                "selling_point": selling_point,
                "shot_type": shot_type,
                "production_mode": production_mode,
                "framing": _infer_framing(role),
                "camera_angle": _infer_camera_angle(role),
                "camera_motion": _infer_camera_motion(role),
                "subject_focus": _infer_subject_focus(role, product, selling_point),
                "asset_source_suggestion": _infer_asset_source(role),
                "subtitle_suggestion": subtitle_suggestion,
                "narration_suggestion": narration_suggestion,
                "template_examples": scene.get("ocr_examples", []),
                "reusable_hint": scene.get("reusable_hint", ""),
                "copywriting_prompt": _copywriting_prompt(role, product),
                "visual_requirements": _visual_requirements(role, product),
                "risk_control": product.get("risk_notes", []),
                "execution_notes": _execution_notes(role, product, selling_point),
                "source_segment_index": scene.get("source_segment_index"),
            }
        )

    script_id = f"script_{uuid4().hex[:12]}"
    return {
        "id": script_id,
        "template_id": template["id"],
        "product_id": product["id"],
        "platform": platform,
        "title_options": title_options,
        "scenes": scenes,
        "material_checklist": build_material_checklist(product, scenes),
        "editing_notes": build_editing_notes(platform, match),
        "trace": {
            "template_version": template.get("version"),
            "template_match_id": match["id"],
            "match_score": match["score"],
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": "gemeiqi.pipeline.build_script_output",
        },
    }


def build_material_checklist(
    product: dict[str, Any],
    scenes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """生成可供人工剪辑或后续生成使用的素材清单。"""

    required_roles = {scene["role"] for scene in scenes}
    checklist = [
        {
            "name": "商品白底或干净背景全貌图",
            "required": any(
                role in required_roles
                for role in ("product_full_view", "product_or_try_on")
            ),
            "source": "existing_asset_or_new_shoot",
            "usage": "用于商品主体介绍、封面帧或开头快速建立商品识别。",
        },
        {
            "name": "上脚走路视频",
            "required": any(
                role in required_roles
                for role in ("try_on", "product_or_try_on")
            ),
            "source": "manual_shoot_recommended",
            "usage": "用于展示比例、脚感和通勤/日常状态。",
        },
        {
            "name": "鞋头、鞋面、鞋底、鞋跟细节图",
            "required": any(
                role in required_roles
                for role in ("detail_proof", "detail_or_selling_point")
            ),
            "source": "existing_asset_or_new_shoot",
            "usage": "用于证明材质、工艺、鞋跟和舒适结构。",
        },
        {
            "name": "通勤或目标场景穿搭画面",
            "required": any(
                role in required_roles
                for role in ("outfit_scene", "transition_or_scene")
            ),
            "source": "manual_shoot_or_low_risk_generation",
            "usage": "用于场景、情绪和人群代入。",
        },
    ]

    for asset_ref in product.get("asset_refs", []):
        checklist.append(
            {
                "name": f"已有关联素材 {asset_ref}",
                "required": False,
                "source": "asset_ref",
                "usage": "可优先作为已有素材池输入，减少重复拍摄。",
            }
        )

    return checklist


def build_editing_notes(platform: str, match: dict[str, Any]) -> list[str]:
    """输出剪辑与发布阶段的执行提醒。"""

    notes = [
        f"当前脚本按 {platform} 短视频节奏组织，建议前 3 秒保留最强钩子。",
        "字幕优先保留短句，避免一屏出现过长信息。",
        "商品主体至少出现 2 到 3 次，避免只讲概念不见鞋。",
    ]
    if match.get("score", 0) < 0.5:
        notes.append("当前模板与商品适配度一般，建议人工重写开头和收尾。")
    if match.get("warnings"):
        notes.append("先处理风险提示里的商品一致性问题，再决定是否做生成镜头。")
    return notes


def _copywriting_prompt(role: str, product: dict[str, Any]) -> str:
    points = _join_cn(product.get("primary_selling_points", []))
    scenarios = _join_cn(product.get("target_scenarios", []))

    if role == "hook":
        return f"用{scenarios}里的真实痛点开头，引出{product['name']}的{points}。"
    if role in {"try_on", "product_or_try_on"}:
        return "强调上脚比例、走路状态和舒适感，不夸张承诺。"
    if role in {"detail_proof", "detail_or_selling_point"}:
        return "用材质、鞋底、跟高等细节证明主卖点。"
    if role == "closing":
        return f"收束到适合{_join_cn(product.get('target_audience', []))}。"
    if role == "transition_or_scene":
        return f"围绕{scenarios}补充场景感和{points}。"
    return f"围绕{product['name']}表达{points}。"


def _visual_requirements(role: str, product: dict[str, Any]) -> list[str]:
    attributes = product.get("attributes", {})
    requirements = [
        "鞋型不得变形",
        "颜色和材质保持一致",
    ]

    if role in {"detail_proof", "detail_or_selling_point"}:
        requirements.append(f"需要清楚展示材质：{attributes.get('material', 'unknown')}")
        requirements.append(f"需要清楚展示跟高：{attributes.get('heel_height_cm', 'unknown')}cm")
    if role in {"try_on", "product_or_try_on"}:
        requirements.append("上脚比例自然，避免脚背和鞋头被拉伸")
    if role == "transition_or_scene":
        requirements.append("场景和商品关系明确，避免只剩空镜或无关转场")

    return requirements


def _join_cn(items: list[str]) -> str:
    return "、".join(items) if items else "核心卖点"


def _resolve_scene_selling_point(
    scene: dict[str, Any],
    template: dict[str, Any],
    index: int,
) -> str:
    selling_point_order = template.get("selling_point_order", [])
    direct = scene.get("selling_point")
    if direct:
        return direct
    if 0 <= index - 1 < len(selling_point_order):
        return selling_point_order[index - 1]
    return selling_point_order[-1] if selling_point_order else ""


def _infer_shot_type(role: str) -> str:
    mapping = {
        "hook": "开场钩子镜头",
        "product_or_try_on": "商品主体/上脚镜头",
        "detail_or_selling_point": "细节特写镜头",
        "transition_or_scene": "场景/转场镜头",
        "closing": "收尾行动镜头",
    }
    return mapping.get(role, "通用镜头")


def _infer_framing(role: str) -> str:
    mapping = {
        "hook": "中近景或特写",
        "product_or_try_on": "全景到中景切换",
        "detail_or_selling_point": "局部特写",
        "transition_or_scene": "中景或全景",
        "closing": "中景或图文收尾",
    }
    return mapping.get(role, "中景")


def _infer_camera_angle(role: str) -> str:
    mapping = {
        "hook": "平视或微俯视",
        "product_or_try_on": "平视为主",
        "detail_or_selling_point": "俯拍或侧拍",
        "transition_or_scene": "平视或跟拍",
        "closing": "平视固定镜头",
    }
    return mapping.get(role, "平视")


def _infer_camera_motion(role: str) -> str:
    mapping = {
        "hook": "快速切入或轻推镜",
        "product_or_try_on": "轻推镜或走动跟拍",
        "detail_or_selling_point": "慢推近或定镜切细节",
        "transition_or_scene": "轻摇镜、走动或转场切换",
        "closing": "定镜或轻微动效",
    }
    return mapping.get(role, "定镜")


def _infer_subject_focus(role: str, product: dict[str, Any], selling_point: str) -> str:
    product_name = product["name"]
    if role == "hook":
        return f"{product_name}对应的核心使用场景与第一眼视觉利益点"
    if role == "product_or_try_on":
        return f"{product_name}上脚比例、鞋型和整体轮廓"
    if role == "detail_or_selling_point":
        return f"{product_name}与“{selling_point or '核心卖点'}”相关的细节部位"
    if role == "closing":
        return f"{product_name}的最终购买理由或活动信息"
    return f"{product_name}在目标场景中的状态与卖点承接"


def _infer_asset_source(role: str) -> str:
    mapping = {
        "hook": "可低风险生成或实拍",
        "product_or_try_on": "优先实拍",
        "detail_or_selling_point": "优先实拍细节素材",
        "transition_or_scene": "实拍、已有素材或低风险生成",
        "closing": "图文动效、活动图或实拍收尾",
    }
    return mapping.get(role, "人工判断")


def _infer_production_mode(role: str, product: dict[str, Any]) -> str:
    if role in {"product_or_try_on", "detail_or_selling_point"}:
        return "建议实拍"
    if role == "closing":
        return "实拍或图文动效"
    if any(
        "材质" in note or "鞋扣" in note or "双带" in note
        for note in product.get("risk_notes", [])
    ):
        return "以实拍为主"
    return "可低风险生成或实拍"


def _subtitle_suggestion(
    role: str,
    product: dict[str, Any],
    selling_point: str,
    platform: str,
) -> str:
    product_name = product["name"]
    if role == "hook":
        return f"如果你也想要{selling_point or '更舒服的通勤鞋'}，这双{product_name}可以先看。"
    if role == "product_or_try_on":
        return f"{product_name}上脚先看比例和整体状态。"
    if role == "detail_or_selling_point":
        return f"重点看这段怎么证明“{selling_point or '核心卖点'}”。"
    if role == "closing":
        return f"{platform}发布版收尾可放活动信息或购买理由。"
    return f"补充展示{selling_point or '商品卖点'}。"


def _narration_suggestion(
    role: str,
    product: dict[str, Any],
    selling_point: str,
    platform: str,
) -> str:
    points = _join_cn(product.get("primary_selling_points", []))
    if role == "hook":
        return f"先用一句真实场景切入，再抛出{product['name']}的核心优势。"
    if role == "product_or_try_on":
        return f"这里口播不要堆信息，先让用户看到{product['name']}上脚效果。"
    if role == "detail_or_selling_point":
        return f"把“{selling_point or points}”说具体，最好有细节支撑。"
    if role == "closing":
        return f"收尾统一到购买理由、适合人群或 {platform} 活动信息。"
    return f"承接前后文，继续围绕{points}推进。"


def _execution_notes(role: str, product: dict[str, Any], selling_point: str) -> list[str]:
    notes = [
        "同一段内尽量只表达一个主要信息点。",
        "字幕与画面重点保持一致，不要字幕讲舒适、画面却只拍远景。",
    ]
    if role == "product_or_try_on":
        notes.append("上脚段优先展示自然步态，避免站桩式摆拍。")
    if role == "detail_or_selling_point":
        notes.append(f"细节段优先围绕“{selling_point or '核心卖点'}”选择部位。")
    if role == "transition_or_scene":
        notes.append("场景段不要只做空镜，尽量保留商品主体或穿着状态。")
    if role == "closing":
        notes.append("收尾信息控制在 1 到 2 个重点，避免信息过载。")
    if any("鞋型" in note for note in product.get("risk_notes", [])):
        notes.append("拍摄时避免广角近距离导致鞋型失真。")
    return notes
