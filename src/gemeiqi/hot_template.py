"""爆款视频模板提炼与商品适配。"""

from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from gemeiqi.repository import dump_json

BLUEPRINTS: dict[int, dict[str, Any]] = {
    1: {
        "role": "hook",
        "visual_type": "model_feet_walk_in_hook",
        "subject": "成年女性模特脚部、小腿和下半身穿搭",
        "model_visibility": "脚部和小腿必须可见，可短暂带到下半身穿搭",
        "product_visibility": "双脚鞋款在开头 1 秒内清楚出现",
        "framing": "低机位脚部近景，竖屏中下部留给鞋",
        "camera_angle": "略低角度或平视脚部",
        "camera_motion": "轻微跟拍或短推镜",
        "action": "模特穿鞋走入画面并停步，制造开头停留",
        "setting": "室内通勤穿搭或干净生活化空间",
        "copy_function": "用偏好或舒适痛点建立停留理由",
        "fixed_parts": ["模特上脚", "走入停步", "脚部低机位", "开头快速见鞋"],
        "replaceable_parts": ["鞋款", "字幕文案", "模特服装", "室内背景"],
        "generation_risk": "medium",
    },
    2: {
        "role": "product_or_try_on",
        "visual_type": "low_angle_try_on_walk",
        "subject": "成年女性模特双脚、小腿和鞋款",
        "model_visibility": "双脚和小腿连续可见",
        "product_visibility": "鞋头、鞋面和扣带需要在走动中可辨认",
        "framing": "低机位脚部近景到中近景",
        "camera_angle": "低机位平视脚部",
        "camera_motion": "跟随脚步轻微移动",
        "action": "模特连续走两到三步，展示上脚比例和走路状态",
        "setting": "通勤或日常出行空间",
        "copy_function": "证明上脚比例、舒适和场景百搭",
        "fixed_parts": ["连续走路", "上脚比例", "双脚可见", "鞋款清晰"],
        "replaceable_parts": ["鞋款", "裤袜/裙装搭配", "字幕卖点"],
        "generation_risk": "medium",
    },
    3: {
        "role": "detail_or_selling_point",
        "visual_type": "on_foot_detail_closeup",
        "subject": "穿在脚上的鞋头、鞋面和扣带细节",
        "model_visibility": "至少一只穿鞋的脚完整可见",
        "product_visibility": "鞋头、扣带、皮面光泽必须清楚",
        "framing": "穿在脚上的局部特写",
        "camera_angle": "侧前方近景或轻俯拍",
        "camera_motion": "慢推近或轻微横移",
        "action": "脚轻微转动，展示鞋头、扣带和皮面",
        "setting": "干净地面或室内试穿环境",
        "copy_function": "用细节证明商品质感和穿脱便利",
        "fixed_parts": ["穿在脚上的细节", "鞋头和扣带特写", "不能变成静物"],
        "replaceable_parts": ["鞋款细节", "细节卖点字幕", "背景地面"],
        "generation_risk": "high",
    },
    4: {
        "role": "transition_or_scene",
        "visual_type": "strap_adjust_or_put_on",
        "subject": "模特脚部、手部和鞋扣带",
        "model_visibility": "脚必须在鞋内，手部只作为辅助动作",
        "product_visibility": "扣带结构和穿脱动作需要清楚",
        "framing": "脚部近景",
        "camera_angle": "轻俯拍或侧前方",
        "camera_motion": "定镜或轻微推近",
        "action": "手部整理扣带或表现穿脱便利",
        "setting": "室内试穿、玄关或更衣场景",
        "copy_function": "证明穿脱方便和鞋面结构",
        "fixed_parts": ["鞋穿在脚上", "扣带整理", "手部短暂入镜"],
        "replaceable_parts": ["扣带卖点", "室内场景", "字幕"],
        "generation_risk": "high",
    },
    5: {
        "role": "transition_or_scene",
        "visual_type": "commute_walk_sequence",
        "subject": "成年女性模特穿鞋走动的下半身",
        "model_visibility": "双脚、小腿和下半身穿搭连续可见",
        "product_visibility": "走动中鞋款保持清晰，不被长裙或裤脚完全遮挡",
        "framing": "下半身中近景和脚部近景组合",
        "camera_angle": "平视或低机位跟拍",
        "camera_motion": "走动跟拍",
        "action": "模特在通勤/日常场景连续走动",
        "setting": "通勤走廊、街边、办公室或室内过道",
        "copy_function": "强化久走舒适和日常百搭",
        "fixed_parts": ["通勤走动", "下半身穿搭", "鞋款不被遮挡"],
        "replaceable_parts": ["场景", "穿搭", "舒适卖点字幕"],
        "generation_risk": "medium",
    },
    6: {
        "role": "transition_or_scene",
        "visual_type": "side_profile_pause_or_seated",
        "subject": "模特穿鞋停步或坐下时的侧面鞋型",
        "model_visibility": "脚踝、小腿和鞋口关系自然",
        "product_visibility": "侧面鞋型、低跟和鞋头轮廓可见",
        "framing": "侧面脚部近景",
        "camera_angle": "侧拍低机位",
        "camera_motion": "慢推或定镜",
        "action": "模特停步、轻抬脚或坐下展示侧面鞋型",
        "setting": "室内椅边、办公室或通勤场景",
        "copy_function": "证明柔软、轻便和不易变形",
        "fixed_parts": ["侧面鞋型", "脚踝连续", "动作克制"],
        "replaceable_parts": ["场景", "袜子或裤装", "柔软卖点字幕"],
        "generation_risk": "high",
    },
    7: {
        "role": "transition_or_scene",
        "visual_type": "step_transition",
        "subject": "模特穿鞋经过镜头或短暂停步",
        "model_visibility": "至少一只穿鞋脚经过画面中心",
        "product_visibility": "鞋款在转场中短暂清楚可见",
        "framing": "脚部近景转场",
        "camera_angle": "低机位",
        "camera_motion": "脚步经过镜头形成遮挡或切换",
        "action": "脚步经过镜头或轻微转身，服务后续拼接",
        "setting": "与前后段一致的生活化空间",
        "copy_function": "提供节奏转场，避免画面单调",
        "fixed_parts": ["脚步转场", "鞋穿在脚上", "短促节奏"],
        "replaceable_parts": ["转场背景", "脚步方向", "字幕有无"],
        "generation_risk": "medium",
    },
    8: {
        "role": "closing",
        "visual_type": "try_on_freeze_for_cta",
        "subject": "模特穿鞋自然站立的双脚和下半身",
        "model_visibility": "双脚自然站立，画面稳定",
        "product_visibility": "鞋款清晰可见，留出文案空间",
        "framing": "脚部或下半身中近景",
        "camera_angle": "平视或轻低机位",
        "camera_motion": "稳定停顿",
        "action": "模特停步定格，便于叠加活动和转化文案",
        "setting": "干净背景或通勤穿搭空间",
        "copy_function": "承接转化信息和购买理由",
        "fixed_parts": ["稳定停顿", "鞋款清楚", "留字幕空间"],
        "replaceable_parts": ["活动文案", "价格信息", "背景"],
        "generation_risk": "medium",
    },
}


def build_hot_video_template(
    analysis: dict[str, Any],
    template_id: str,
    review_status: str = "manual_seed",
) -> dict[str, Any]:
    """从本地视频分析结果生成可复用爆款镜头模板。"""

    scenes = []
    for segment in analysis.get("segments", []):
        index = int(segment["index"])
        blueprint = BLUEPRINTS.get(index, _fallback_blueprint(segment))
        scenes.append(_build_scene_template(segment, blueprint))

    return {
        "id": template_id,
        "name": "女鞋爆款上脚试穿镜头模板",
        "version": "0.2.0-manual-seed",
        "category": "women_shoes",
        "platform": "douyin",
        "source_video": analysis.get("video", {}).get("path", ""),
        "source_video_meta": {
            key: analysis.get("video", {}).get(key)
            for key in ("duration_seconds", "width", "height", "fps")
        },
        "review_status": review_status,
        "template_summary": (
            "从爆款视频提炼出的女鞋上脚短视频模板，重点复用脚部低机位、"
            "模特真实上脚、通勤走动、穿在脚上的细节证明和结尾转化停顿。"
        ),
        "scenes": scenes,
        "global_rules": {
            "fixed": ["真人模特上脚", "鞋穿在脚上", "竖屏快节奏", "商品细节不跑偏"],
            "replaceable": ["鞋款", "卖点文案", "模特服装", "室内/通勤场景"],
            "reference_policy": {
                "product_reference_priority": "商品图永远高于爆款源帧",
                "hot_video_reference_usage": "只用于构图、机位、动作节奏和人物露出范围",
                "seedance_2_strategy": "默认 2 张商品图 + 2 张爆款分镜帧",
            },
            "quality_gate": [
                "必须有成年女性模特",
                "鞋必须穿在脚上",
                "鞋款关键结构必须接近目标 SKU",
                "必须匹配源模板的构图和动作",
                "不合格片段单独重跑，不进入成片",
            ],
        },
        "trace": {
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": "gemeiqi.hot_template.build_hot_video_template",
        },
    }


def build_product_template_adaptation(
    hot_template: dict[str, Any],
    product: dict[str, Any],
) -> dict[str, Any]:
    """把爆款镜头模板适配到具体女鞋商品。"""

    product_features = _product_features(product)
    adaptations = []
    for scene in hot_template.get("scenes", []):
        adaptations.append(
            {
                "scene_index": scene["index"],
                "role": scene["role"],
                "source_template_scene_id": scene["id"],
                "target_visual": _target_visual(scene, product, product_features),
                "template_reuse_score": scene.get("template_reuse_score", 0.0),
                "stability_tier": _stability_tier(scene),
                "must_keep_product_features": product_features,
                "must_follow_template": {
                    "visual_type": scene["visual_type"],
                    "framing": scene["camera"]["framing"],
                    "camera_angle": scene["camera"]["angle"],
                    "camera_motion": scene["camera"]["motion"],
                    "action": scene["action"],
                    "model_visibility": scene["model_visibility"],
                    "product_visibility": scene["product_visibility"],
                    "fixed_parts": scene["fixed_parts"],
                },
                "acceptable_variation": scene["replaceable_parts"],
                "seedance_reference_plan": {
                    "product_reference_slots": ["商品全貌图", "鞋头/扣带细节图"],
                    "hot_video_reference_slots": [
                        candidate.get("label", "")
                        for candidate in scene.get("source_reference_candidates", [])[:2]
                    ],
                    "reference_mix_rule": "先满足商品一致性，再满足爆款镜头结构",
                    "focus_dimensions": scene.get("product_consistency_focus", []),
                },
                "generation_success_definition": [
                    "鞋款外观首先像商品图",
                    "构图和动作其次像爆款源分镜",
                    "模特上脚真实，帧间不漂移",
                ],
                "not_acceptable": _not_acceptable(scene, product),
                "quality_checks": scene["quality_checks"],
                "retry_policy": {
                    "max_retries": 3,
                    "retry_when": [
                        "没有模特或没有脚",
                        "鞋没有穿在脚上",
                        "鞋型、扣带、鞋头或颜色明显错误",
                        "镜头构图不符合源模板",
                    ],
                },
            }
        )

    return {
        "id": f"adapt_{hot_template['id']}_{product['id']}",
        "template_id": hot_template["id"],
        "product_id": product["id"],
        "product_name": product["name"],
        "scene_adaptations": adaptations,
        "trace": {
            "generated_at": datetime.now(UTC).isoformat(),
            "generator": "gemeiqi.hot_template.build_product_template_adaptation",
        },
    }


def write_template_review_board(
    path: Path,
    hot_template: dict[str, Any],
    analysis_dir: Path,
) -> None:
    """写出便于人工审核和修正的爆款模板看板。"""

    rows = []
    for scene in hot_template.get("scenes", []):
        frame_cells = []
        product_focus = "、".join(scene.get("product_consistency_focus", []))
        for frame in scene.get("source_frames", []):
            image_path = analysis_dir / frame["image_path"]
            frame_cells.append(
                "<figure>"
                f"<img src='{escape(str(image_path))}' alt='{escape(frame['label'])}'>"
                f"<figcaption>{escape(frame['label'])} {frame['timestamp_seconds']}s</figcaption>"
                "</figure>"
            )
        heading = (
            f"<h2>分镜 {scene['index']} · {escape(scene['role'])} · "
            f"{escape(scene['visual_type'])}</h2>"
        )
        rows.append(
            "<section>"
            f"{heading}"
            f"<div class='frames'>{''.join(frame_cells)}</div>"
            "<dl>"
            f"<dt>主体</dt><dd>{escape(scene['subject'])}</dd>"
            f"<dt>构图</dt><dd>{escape(scene['camera']['framing'])}</dd>"
            f"<dt>动作</dt><dd>{escape(scene['action'])}</dd>"
            f"<dt>模板复用分</dt><dd>{scene.get('template_reuse_score', 0.0)}</dd>"
            f"<dt>商品一致性重点</dt><dd>{escape(product_focus)}</dd>"
            f"<dt>固定项</dt><dd>{escape('、'.join(scene['fixed_parts']))}</dd>"
            f"<dt>可替换项</dt><dd>{escape('、'.join(scene['replaceable_parts']))}</dd>"
            f"<dt>质量检查</dt><dd>{escape('、'.join(scene['quality_checks']))}</dd>"
            f"<dt>OCR</dt><dd>{escape(' / '.join(scene.get('source_ocr_texts', [])))}</dd>"
            "</dl>"
            "</section>"
        )

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{escape(hot_template['name'])}</title>
  <style>
    body {{ font-family: system-ui, "Microsoft YaHei", sans-serif; margin: 24px; color: #1f2328; }}
    h1 {{ font-size: 24px; }}
    section {{ border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    .frames {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }}
    img {{ width: 100%; border-radius: 6px; border: 1px solid #d0d7de; }}
    figure {{ margin: 0; }}
    figcaption {{ font-size: 12px; color: #57606a; }}
    dt {{ font-weight: 700; margin-top: 8px; }}
    dd {{ margin-left: 0; }}
  </style>
</head>
<body>
  <h1>{escape(hot_template['name'])}</h1>
  <p>{escape(hot_template['template_summary'])}</p>
  {''.join(rows)}
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def write_hot_template_outputs(
    output_dir: Path,
    hot_template: dict[str, Any],
    analysis_dir: Path,
) -> None:
    """写出模板 JSON 和人工审核看板。"""

    dump_json(output_dir / "hot_video_template.json", hot_template)
    write_template_review_board(
        output_dir / "hot_video_template_review.html",
        hot_template,
        analysis_dir,
    )


def _build_scene_template(segment: dict[str, Any], blueprint: dict[str, Any]) -> dict[str, Any]:
    index = int(segment["index"])
    return {
        "id": f"scene_tpl_{index:04d}",
        "index": index,
        "role": blueprint["role"],
        "source_segment": {
            "index": index,
            "start": segment.get("start"),
            "end": segment.get("end"),
            "duration_seconds": segment.get("duration_seconds"),
            "clip_path": segment.get("clip_path", ""),
            "cover_frame": segment.get("cover_frame", ""),
        },
        "source_frames": segment.get("review_frames", []),
        "source_reference_candidates": segment.get("seedance_reference_candidates", []),
        "source_ocr_texts": segment.get("ocr_texts", []),
        "expression_stage": segment.get("expression_stage", ""),
        "template_reuse_score": segment.get("template_reuse_score", 0.0),
        "visual_type": blueprint["visual_type"],
        "subject": blueprint["subject"],
        "model_visibility": blueprint["model_visibility"],
        "product_visibility": blueprint["product_visibility"],
        "camera": {
            "framing": blueprint["framing"],
            "angle": blueprint["camera_angle"],
            "motion": blueprint["camera_motion"],
        },
        "action": blueprint["action"],
        "setting": blueprint["setting"],
        "copy_function": blueprint["copy_function"],
        "fixed_parts": blueprint["fixed_parts"],
        "replaceable_parts": blueprint["replaceable_parts"],
        "product_consistency_focus": segment.get("product_consistency_focus", []),
        "reference_usage": {
            "purpose": "爆款结构参考",
            "allowed": ["构图", "机位", "动作节奏", "人物露出范围"],
            "forbidden": ["替换商品鞋款", "照搬字幕", "照搬商品卖点"],
        },
        "stability_rules": [
            "商品外观必须后续由商品图锁定，不允许被模板图带偏",
            "模板只负责镜头结构迁移，不负责商品样式迁移",
            "高风险细节镜头允许单独重跑，不进入整包拼接前必须人工过审",
        ],
        "generation_requirements": _generation_requirements(blueprint),
        "negative_requirements": _negative_requirements(),
        "quality_checks": _quality_checks(blueprint),
        "generation_risk": blueprint["generation_risk"],
        "review_status": "manual_seed_needs_visual_check",
    }


def _generation_requirements(blueprint: dict[str, Any]) -> list[str]:
    return [
        f"画面类型必须是：{blueprint['visual_type']}",
        f"主体必须是：{blueprint['subject']}",
        f"构图必须遵循：{blueprint['framing']}",
        f"动作必须遵循：{blueprint['action']}",
        f"商品可见性要求：{blueprint['product_visibility']}",
    ]


def _negative_requirements() -> list[str]:
    return [
        "不要生成白底商品详情页",
        "不要生成没有模特脚部的孤立鞋子",
        "不要手拿鞋、桌面摆拍或鞋盒展示",
        "不要改变鞋型、颜色、扣带数量、鞋头结构和材质光泽",
        "不要出现男性模特、儿童、赤脚、拖鞋或运动鞋",
    ]


def _quality_checks(blueprint: dict[str, Any]) -> list[str]:
    return [
        "是否出现成年女性模特",
        "鞋是否真实穿在脚上",
        f"是否符合源模板构图：{blueprint['framing']}",
        f"是否完成源模板动作：{blueprint['action']}",
        "目标商品颜色、鞋头、扣带和材质是否正确",
        "是否可以直接进入成片，不能则记录重跑原因",
    ]


def _product_features(product: dict[str, Any]) -> list[str]:
    attributes = product.get("attributes", {})
    features = [
        f"商品名称：{product['name']}",
        f"鞋型：{product.get('shoe_type', '')}",
        f"颜色：{attributes.get('color', '')}",
        f"材质：{attributes.get('material', '')}",
        f"鞋头：{attributes.get('toe_shape', '')}",
        f"闭合方式：{attributes.get('closure', '')}",
        f"跟高：{attributes.get('heel_height_cm', '')}cm",
    ]
    features.extend(product.get("detail_features", []))
    return [feature for feature in features if feature and not feature.endswith("：")]


def _target_visual(scene: dict[str, Any], product: dict[str, Any], features: list[str]) -> str:
    return (
        f"按源模板“{scene['visual_type']}”生成：成年女性模特真实穿着"
        f"{product['name']}，{scene['action']}。必须保留 {'、'.join(features)}。"
    )


def _not_acceptable(scene: dict[str, Any], product: dict[str, Any]) -> list[str]:
    return [
        "没有模特",
        "没有脚或鞋没有穿在脚上",
        "只出现商品静物图或局部鞋面动画",
        f"不像 {product['name']}",
        "扣带数量、鞋头形状、颜色或材质错误",
        f"不符合源模板动作：{scene['action']}",
        f"不符合源模板构图：{scene['camera']['framing']}",
    ]


def _fallback_blueprint(segment: dict[str, Any]) -> dict[str, Any]:
    role = segment.get("role_guess", "transition_or_scene")
    return {
        "role": role,
        "visual_type": "generic_try_on_scene",
        "subject": "成年女性模特脚部和鞋款",
        "model_visibility": "脚部和鞋款必须可见",
        "product_visibility": "鞋款清楚可辨",
        "framing": "脚部中近景",
        "camera_angle": "平视或低机位",
        "camera_motion": "轻微移动",
        "action": "模特穿鞋完成自然展示动作",
        "setting": "生活化女鞋试穿场景",
        "copy_function": "承接商品卖点",
        "fixed_parts": ["模特上脚", "鞋款清楚", "动作自然"],
        "replaceable_parts": ["鞋款", "场景", "字幕"],
        "generation_risk": "medium",
    }


def _stability_tier(scene: dict[str, Any]) -> str:
    score = float(scene.get("template_reuse_score", 0.0))
    role = scene.get("role", "")
    if score >= 0.9 and role in {"hook", "product_or_try_on", "closing"}:
        return "stable"
    if score >= 0.8:
        return "cautious"
    return "risky"
