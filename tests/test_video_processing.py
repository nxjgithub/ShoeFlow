from __future__ import annotations

import unittest

from gemeiqi.video_processing import (
    build_template_reference_summary,
    enrich_segments_for_template_reuse,
)


class VideoProcessingTemplateTests(unittest.TestCase):
    def test_enrich_segments_for_template_reuse_adds_reference_candidates(self) -> None:
        segments = [
            {
                "index": 1,
                "role_guess": "hook",
                "duration_seconds": 3.2,
                "ocr_texts": ["如果你也在找一双好穿的玛丽珍"],
                "review_frames": [
                    {"label": "start", "timestamp_seconds": 0.0, "image_path": "a.jpg"},
                    {"label": "middle", "timestamp_seconds": 1.2, "image_path": "b.jpg"},
                    {"label": "end", "timestamp_seconds": 2.9, "image_path": "c.jpg"},
                ],
            },
            {
                "index": 2,
                "role_guess": "transition_or_scene",
                "duration_seconds": 7.5,
                "ocr_texts": [],
                "review_frames": [
                    {"label": "start", "timestamp_seconds": 3.0, "image_path": "d.jpg"},
                ],
            },
        ]

        enrich_segments_for_template_reuse(segments)
        summary = build_template_reference_summary(segments)

        self.assertEqual("opening_hook", segments[0]["expression_stage"])
        self.assertTrue(segments[0]["template_candidate"])
        self.assertGreaterEqual(segments[0]["template_reuse_score"], 0.5)
        self.assertEqual(
            "hot_video_structure",
            segments[0]["seedance_reference_candidates"][0]["purpose"],
        )
        self.assertIn("鞋款快速露出", segments[0]["product_consistency_focus"])
        self.assertIn(1, summary["candidate_segment_indexes"])
        self.assertNotIn(2, summary["candidate_segment_indexes"])
        self.assertGreaterEqual(summary["reference_frame_count"], 2)


if __name__ == "__main__":
    unittest.main()
