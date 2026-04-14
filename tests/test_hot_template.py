from __future__ import annotations

import unittest

from gemeiqi.hot_template import build_hot_video_template, build_product_template_adaptation
from gemeiqi.paths import FIXTURES_DIR
from gemeiqi.repository import load_json


class HotTemplateTests(unittest.TestCase):
    def test_build_hot_video_template_keeps_visual_contract(self) -> None:
        analysis = {
            "video": {"path": "temp_data/demo.mp4", "duration_seconds": 25.0},
            "segments": [
                {
                    "index": 1,
                    "start": 0.0,
                    "end": 4.0,
                    "duration_seconds": 4.0,
                    "clip_path": "segments/segment_0001.mp4",
                    "cover_frame": "frames/frame_0001.jpg",
                    "review_frames": [
                        {
                            "label": "start",
                            "timestamp_seconds": 0.0,
                            "image_path": "segment_frames/start.jpg",
                        }
                    ],
                    "ocr_texts": ["如果你偏爱舒适体验"],
                }
            ],
        }

        hot_template = build_hot_video_template(
            analysis=analysis,
            template_id="tpl_hot_demo",
        )

        self.assertEqual("tpl_hot_demo", hot_template["id"])
        scene = hot_template["scenes"][0]
        self.assertEqual("model_feet_walk_in_hook", scene["visual_type"])
        self.assertIn("模特上脚", scene["fixed_parts"])
        self.assertIn("是否出现成年女性模特", scene["quality_checks"])
        self.assertEqual("segments/segment_0001.mp4", scene["source_segment"]["clip_path"])

    def test_build_product_template_adaptation_adds_product_constraints(self) -> None:
        product = load_json(FIXTURES_DIR / "products.json")[1]
        hot_template = {
            "id": "tpl_hot_demo",
            "scenes": [
                {
                    "id": "scene_tpl_0002",
                    "index": 2,
                    "role": "product_or_try_on",
                    "visual_type": "low_angle_try_on_walk",
                    "camera": {
                        "framing": "低机位脚部近景",
                        "angle": "低机位",
                        "motion": "跟拍",
                    },
                    "action": "模特连续走两到三步",
                    "model_visibility": "双脚和小腿连续可见",
                    "product_visibility": "鞋头和扣带可辨认",
                    "fixed_parts": ["连续走路", "上脚比例"],
                    "replaceable_parts": ["鞋款", "字幕"],
                    "quality_checks": ["是否出现成年女性模特"],
                }
            ],
        }

        adaptation = build_product_template_adaptation(hot_template=hot_template, product=product)

        self.assertEqual(product["id"], adaptation["product_id"])
        scene = adaptation["scene_adaptations"][0]
        self.assertIn("复古双带玛丽珍单鞋", scene["target_visual"])
        self.assertIn("双带扣带", scene["must_keep_product_features"])
        self.assertEqual("低机位脚部近景", scene["must_follow_template"]["framing"])
        self.assertIn("鞋没有穿在脚上", scene["retry_policy"]["retry_when"])


if __name__ == "__main__":
    unittest.main()
