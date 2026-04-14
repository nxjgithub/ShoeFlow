from __future__ import annotations

import unittest

from gemeiqi.quality_review import build_generation_quality_review


class QualityReviewTests(unittest.TestCase):
    def test_build_generation_quality_review_keeps_template_checks_and_task_status(self) -> None:
        plan = {
            "id": "seedance_plan_demo",
            "product_id": "sku_maryjane_001",
            "template_adaptation_id": "adapt_tpl_demo",
            "segments": [
                {
                    "scene_index": 2,
                    "role": "product_or_try_on",
                    "generation_mode": "text_to_video_model_tryon",
                    "template_adaptation": {
                        "visual_type": "low_angle_try_on_walk",
                        "framing": "低机位脚部近景",
                        "action": "模特穿鞋向前走两步",
                        "quality_checks": ["鞋扣带清晰可见"],
                    },
                }
            ],
        }
        tasks = {
            "tasks": [
                {
                    "scene_index": 2,
                    "task_id": "task_demo_002",
                    "status": "succeeded",
                }
            ]
        }

        review = build_generation_quality_review(plan=plan, tasks=tasks)

        self.assertEqual("seedance_plan_demo", review["plan_id"])
        self.assertEqual("adapt_tpl_demo", review["template_adaptation_id"])
        self.assertEqual(1, len(review["scenes"]))
        scene = review["scenes"][0]
        self.assertEqual("task_demo_002", scene["task_id"])
        self.assertEqual("succeeded", scene["task_status"])
        self.assertFalse(scene["review_result"]["approved_for_final"])
        self.assertIn("low_angle_try_on_walk", scene["retry_hint"])
        checks = [item["check"] for item in scene["required_checks"]]
        self.assertIn("鞋扣带清晰可见", checks)
        self.assertIn("鞋是否真实穿在脚上", checks)


if __name__ == "__main__":
    unittest.main()
