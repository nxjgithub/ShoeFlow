from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from gemeiqi.cli import generate_script_drafts_for_products
from gemeiqi.paths import FIXTURES_DIR
from gemeiqi.pipeline import build_script_output, score_template_for_product
from gemeiqi.repository import load_json
from gemeiqi.video_renderer import build_timeline


class PipelineTests(unittest.TestCase):
    def test_demo_script_keeps_traceability(self) -> None:
        product = load_json(FIXTURES_DIR / "products.json")[0]
        template = load_json(FIXTURES_DIR / "templates.json")[0]

        match = score_template_for_product(template, product, "douyin")
        script = build_script_output(product, template, match, "douyin")

        self.assertEqual(product["id"], script["product_id"])
        self.assertEqual(template["id"], script["template_id"])
        self.assertEqual(match["id"], script["trace"]["template_match_id"])
        self.assertGreaterEqual(len(script["scenes"]), 1)
        self.assertGreaterEqual(len(script["material_checklist"]), 1)
        self.assertGreaterEqual(len(script["editing_notes"]), 1)
        first_scene = script["scenes"][0]
        self.assertIn("shot_type", first_scene)
        self.assertIn("production_mode", first_scene)
        self.assertIn("framing", first_scene)
        self.assertIn("camera_angle", first_scene)
        self.assertIn("camera_motion", first_scene)
        self.assertIn("subject_focus", first_scene)
        self.assertIn("asset_source_suggestion", first_scene)
        self.assertIn("subtitle_suggestion", first_scene)
        self.assertIn("narration_suggestion", first_scene)
        self.assertIn("execution_notes", first_scene)

    def test_template_draft_roles_can_generate_script(self) -> None:
        product = load_json(FIXTURES_DIR / "products.json")[0]
        template = {
            "id": "tpl_draft_demo",
            "name": "测试模板",
            "version": "0.1.0-draft",
            "platforms": ["douyin"],
            "selling_point_order": ["舒适久走", "场景百搭"],
            "scene_structure": [
                {"role": "hook", "duration_seconds": 3, "goal": "开头"},
                {"role": "product_or_try_on", "duration_seconds": 4, "goal": "上脚"},
                {"role": "detail_or_selling_point", "duration_seconds": 4, "goal": "细节"},
                {"role": "transition_or_scene", "duration_seconds": 3, "goal": "场景"},
                {"role": "closing", "duration_seconds": 2, "goal": "收尾"},
            ],
        }

        match = score_template_for_product(template, product, "douyin")
        script = build_script_output(product, template, match, "douyin")

        role_to_scene = {scene["role"]: scene for scene in script["scenes"]}
        self.assertIn("product_or_try_on", role_to_scene)
        self.assertIn("detail_or_selling_point", role_to_scene)
        self.assertIn("transition_or_scene", role_to_scene)
        try_on_requirements = "；".join(role_to_scene["product_or_try_on"]["visual_requirements"])
        detail_requirements = "；".join(
            role_to_scene["detail_or_selling_point"]["visual_requirements"]
        )
        self.assertIn("上脚比例自然", try_on_requirements)
        self.assertIn("材质", detail_requirements)
        self.assertEqual("建议实拍", role_to_scene["product_or_try_on"]["production_mode"])
        self.assertEqual("细节特写镜头", role_to_scene["detail_or_selling_point"]["shot_type"])
        self.assertEqual("全景到中景切换", role_to_scene["product_or_try_on"]["framing"])
        self.assertIn("上脚", role_to_scene["product_or_try_on"]["subject_focus"])

    def test_generate_script_drafts_for_products_accepts_template_argument(self) -> None:
        template = {
            "id": "tpl_draft_demo",
            "name": "测试模板",
            "version": "0.1.0-draft",
            "source_analysis_ids": ["analysis_demo"],
            "platforms": ["douyin"],
            "hook_type": "preference_or_comfort_hook",
            "scene_structure": [
                {"role": "hook", "duration_seconds": 3, "goal": "开头"},
                {"role": "product_or_try_on", "duration_seconds": 4, "goal": "上脚"},
            ],
            "selling_point_order": ["舒适久走", "场景百搭"],
            "copywriting_style": {"tone": "口语化种草", "pace": "中快节奏", "keywords": []},
            "product_variables": ["shoe_type", "target_scenarios"],
        }
        output_dir = Path("data/runtime/test_generate_script_drafts")
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        count = generate_script_drafts_for_products(
            output_dir=output_dir,
            product_ids=["sku_loafer_001"],
            template=template,
        )

        self.assertEqual(1, count)
        self.assertTrue((output_dir / "script_drafts" / "matches_summary.md").exists())
        self.assertTrue(
            (output_dir / "script_drafts" / "sku_loafer_001" / "script_output.md").exists()
        )
        shutil.rmtree(output_dir)

    def test_build_timeline_maps_scene_to_segment_clip(self) -> None:
        analysis = {
            "segments": [
                {"index": 1, "clip_path": "segments/segment_0001.mp4", "duration_seconds": 3.0},
                {"index": 2, "clip_path": "segments/segment_0002.mp4", "duration_seconds": 4.0},
            ]
        }
        script_output = {
            "scenes": [
                {
                    "index": 1,
                    "source_segment_index": 1,
                    "duration_seconds": 3.0,
                    "role": "hook",
                    "shot_type": "开场钩子镜头",
                    "subtitle_suggestion": "先看这双鞋",
                    "narration_suggestion": "先讲使用场景",
                    "selling_point": "舒适久走",
                }
            ]
        }

        timeline = build_timeline(analysis=analysis, script_output=script_output)

        self.assertEqual(1, len(timeline))
        self.assertEqual("segments/segment_0001.mp4", timeline[0]["clip_path"])
        self.assertEqual("舒适久走", timeline[0]["selling_point"])


if __name__ == "__main__":
    unittest.main()
