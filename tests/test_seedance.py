from __future__ import annotations

import unittest
from pathlib import Path

from gemeiqi.repository import load_json
from gemeiqi.seedance import (
    DEFAULT_MODEL,
    GENERATION_PROFILE_TRYON,
    build_seedance_plan,
    resolve_reference_images,
    submit_seedance_plan,
)


class SeedancePlanTests(unittest.TestCase):
    def test_resolve_reference_images_from_sample_assets(self) -> None:
        product = load_json(Path("examples/fixtures/products.json"))[1]

        images = resolve_reference_images(product)

        self.assertEqual(2, len(images))
        self.assertTrue(images[0]["local_path"].endswith(".jpg"))
        self.assertEqual("sample_asset", images[0]["source"])

    def test_build_seedance_plan_keeps_traceability(self) -> None:
        product = load_json(Path("examples/fixtures/products.json"))[1]
        analysis = {
            "video": {"path": "temp_data/4f9893387224c46272b063713119596f.mp4"},
            "segments": [
                {
                    "index": 1,
                    "clip_path": "segments/segment_0001.mp4",
                    "cover_frame": "frames/frame_0001.jpg",
                    "ocr_texts": ["如果你也想要更舒适的通勤体验"],
                }
            ],
        }
        script_output = {
            "id": "script_demo_001",
            "template_id": "tpl_demo_001",
            "product_id": product["id"],
            "scenes": [
                {
                    "index": 1,
                    "role": "hook",
                    "duration_seconds": 3.0,
                    "selling_point": "通勤舒适",
                    "subtitle_suggestion": "先看这双双扣玛丽珍的鞋型和上脚气质。",
                    "narration_suggestion": "先用一句通勤场景切入，再把鞋子主体推到视觉中心。",
                    "source_segment_index": 1,
                }
            ],
        }
        reference_images = resolve_reference_images(product)

        plan = build_seedance_plan(
            analysis=analysis,
            script_output=script_output,
            product=product,
            reference_images=reference_images,
            output_dir=Path("data/runtime/seedance_test"),
            public_reference_urls=["https://example.com/image-1.jpg"],
        )

        self.assertEqual(product["id"], plan["product_id"])
        self.assertEqual(DEFAULT_MODEL, plan["model"])
        self.assertEqual(1, len(plan["segments"]))
        first_segment = plan["segments"][0]
        self.assertEqual(1, first_segment["source_hot_video"]["segment_index"])
        self.assertIn(product["name"], first_segment["prompt"])
        self.assertIn("双扣带", first_segment["negative_prompt"])
        payload = first_segment["request_payload"]
        self.assertEqual(DEFAULT_MODEL, payload["model"])
        self.assertEqual("text", payload["content"][0]["type"])
        self.assertEqual("image_url", payload["content"][1]["type"])
        self.assertEqual("first_frame", payload["content"][1]["role"])
        self.assertEqual(
            "https://example.com/image-1.jpg",
            payload["content"][1]["image_url"]["url"],
        )

    def test_build_seedance_plan_uses_data_url_when_public_url_missing(self) -> None:
        product = load_json(Path("examples/fixtures/products.json"))[1]
        analysis = {"video": {"path": "temp_data/demo.mp4"}, "segments": []}
        script_output = {
            "id": "script_demo_002",
            "template_id": "tpl_demo_001",
            "product_id": product["id"],
            "scenes": [
                {
                    "index": 1,
                    "role": "hook",
                    "duration_seconds": 2.0,
                    "selling_point": "复古通勤",
                    "source_segment_index": 1,
                }
            ],
        }
        reference_images = resolve_reference_images(product)

        plan = build_seedance_plan(
            analysis=analysis,
            script_output=script_output,
            product=product,
            reference_images=reference_images,
            output_dir=Path("data/runtime/seedance_test"),
        )

        image_url = plan["segments"][0]["request_payload"]["content"][1]["image_url"]["url"]
        self.assertTrue(image_url.startswith("data:image/jpeg;base64,"))

    def test_model_tryon_profile_uses_text_to_video_for_tryon_roles(self) -> None:
        product = load_json(Path("examples/fixtures/products.json"))[1]
        analysis = {"video": {"path": "temp_data/demo.mp4"}, "segments": []}
        script_output = {
            "id": "script_demo_tryon",
            "template_id": "tpl_demo_001",
            "product_id": product["id"],
            "scenes": [
                {
                    "index": 1,
                    "role": "product_or_try_on",
                    "duration_seconds": 3.0,
                    "selling_point": "通勤百搭",
                    "source_segment_index": 2,
                },
                {
                    "index": 2,
                    "role": "detail_or_selling_point",
                    "duration_seconds": 2.0,
                    "selling_point": "双带扣带",
                    "source_segment_index": 3,
                },
            ],
        }
        reference_images = resolve_reference_images(product)

        plan = build_seedance_plan(
            analysis=analysis,
            script_output=script_output,
            product=product,
            reference_images=reference_images,
            output_dir=Path("data/runtime/seedance_test"),
            generation_profile=GENERATION_PROFILE_TRYON,
        )

        tryon_segment = plan["segments"][0]
        self.assertEqual("text_to_video_model_tryon", tryon_segment["generation_mode"])
        self.assertEqual("medium", tryon_segment["risk_level"])
        self.assertTrue(tryon_segment["submit_recommended"])
        self.assertIn("模特上脚试穿", tryon_segment["prompt"])
        self.assertIn("成年女性模特", tryon_segment["prompt"])
        self.assertEqual(1, len(tryon_segment["request_payload"]["content"]))
        self.assertEqual("text", tryon_segment["request_payload"]["content"][0]["type"])

        detail_segment = plan["segments"][1]
        self.assertEqual("text_to_video_model_tryon", detail_segment["generation_mode"])
        self.assertIn("穿在脚上的细节近景", detail_segment["prompt"])
        self.assertEqual(1, len(detail_segment["request_payload"]["content"]))

    def test_invalid_model_is_rejected(self) -> None:
        product = load_json(Path("examples/fixtures/products.json"))[1]
        analysis = {"video": {"path": "temp_data/demo.mp4"}, "segments": []}
        script_output = {
            "id": "script_demo_003",
            "template_id": "tpl_demo_001",
            "product_id": product["id"],
            "scenes": [{"index": 1, "role": "hook", "duration_seconds": 2.0}],
        }
        reference_images = resolve_reference_images(product)

        with self.assertRaises(ValueError):
            build_seedance_plan(
                analysis=analysis,
                script_output=script_output,
                product=product,
                reference_images=reference_images,
                output_dir=Path("data/runtime/seedance_test"),
                model="doubao-seed-2-0-pro-260215",
            )

    def test_submit_seedance_plan_can_limit_scene_indexes(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.payloads = []

            def create_task(self, payload: dict) -> dict:
                self.payloads.append(payload)
                return {"id": f"task-{len(self.payloads)}", "status": "submitted"}

        plan = {
            "id": "seedance_plan_demo",
            "segments": [
                {
                    "scene_index": 1,
                    "role": "hook",
                    "submit_recommended": True,
                    "request_payload": {"model": DEFAULT_MODEL, "content": [{"type": "text"}]},
                },
                {
                    "scene_index": 2,
                    "role": "product_or_try_on",
                    "submit_recommended": True,
                    "request_payload": {"model": DEFAULT_MODEL, "content": [{"type": "text"}]},
                },
            ],
        }
        client = FakeClient()

        result = submit_seedance_plan(
            plan=plan,
            output_dir=Path("data/runtime/seedance_submit_test"),
            client=client,  # type: ignore[arg-type]
            scene_indexes=[2],
        )

        self.assertEqual(1, len(client.payloads))
        self.assertEqual("skipped_not_selected", result["tasks"][0]["status"])
        self.assertEqual("submitted", result["tasks"][1]["status"])


if __name__ == "__main__":
    unittest.main()
