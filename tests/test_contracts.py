from __future__ import annotations

import unittest
from pathlib import Path

from gemeiqi.cli import FIXTURE_SPECS
from gemeiqi.contracts import validate_collection
from gemeiqi.ocr import subtitle_texts
from gemeiqi.repository import load_json
from gemeiqi.template_editor import load_template_from_markdown, write_template_editor_markdown
from gemeiqi.video_processing import build_content_template_draft, build_video_analysis_draft


class ContractFixtureTests(unittest.TestCase):
    def test_all_fixture_files_match_contracts(self) -> None:
        for kind, path in FIXTURE_SPECS.items():
            with self.subTest(kind=kind):
                issues = validate_collection(kind, load_json(path))
                self.assertEqual([], [issue.format() for issue in issues])

    def test_video_analysis_draft_matches_contract(self) -> None:
        draft = build_video_analysis_draft(
            result={
                "video": {
                    "path": "temp_data/demo.mp4",
                    "duration_seconds": 3,
                },
                "segments": [
                    {
                        "index": 1,
                        "start": 0,
                        "end": 3,
                        "duration_seconds": 3,
                        "role_guess": "hook",
                        "cover_frame": "frames/frame_0000.jpg",
                        "clip_path": "segments/segment_0001.mp4",
                    }
                ],
            },
            sample_id="vs_demo",
        )

        issues = validate_collection("video_analysis", [draft])

        self.assertEqual([], [issue.format() for issue in issues])

    def test_content_template_draft_matches_contract(self) -> None:
        analysis_draft = build_video_analysis_draft(
            result={
                "video": {
                    "path": "temp_data/demo.mp4",
                    "duration_seconds": 5,
                },
                "segments": [
                    {
                        "index": 1,
                        "start": 0,
                        "end": 2,
                        "duration_seconds": 2,
                        "role_guess": "hook",
                        "cover_frame": "frames/frame_0000.jpg",
                        "clip_path": "segments/segment_0001.mp4",
                        "ocr_texts": ["如果你偏爱舒适体验"],
                    },
                    {
                        "index": 2,
                        "start": 2,
                        "end": 5,
                        "duration_seconds": 3,
                        "role_guess": "closing",
                        "cover_frame": "frames/frame_0001.jpg",
                        "clip_path": "segments/segment_0002.mp4",
                        "ocr_texts": ["超级立减"],
                    },
                ],
            },
            sample_id="vs_demo",
        )
        template_draft = build_content_template_draft(analysis_draft)

        issues = validate_collection("template", [template_draft])

        self.assertEqual([], [issue.format() for issue in issues])

    def test_template_editor_markdown_roundtrip(self) -> None:
        template = {
            "id": "tpl_roundtrip",
            "name": "回写测试模板",
            "version": "0.1.0-draft",
            "source_analysis_ids": ["analysis_demo"],
            "platforms": ["douyin"],
            "hook_type": "preference_or_comfort_hook",
            "scene_structure": [
                {
                    "source_segment_index": 1,
                    "role": "hook",
                    "duration_seconds": 3.0,
                    "goal": "开头",
                    "reusable_hint": "替换钩子表达",
                    "ocr_examples": ["如果你偏爱舒适体验"],
                }
            ],
            "selling_point_order": ["舒适久走", "场景百搭"],
            "copywriting_style": {
                "tone": "口语化种草",
                "pace": "中快节奏",
                "keywords": ["舒适", "通勤"],
            },
            "product_variables": ["shoe_type", "target_scenarios"],
            "template_summary": "自动草稿摘要",
            "reuse_notes": ["先复用结构，再替换卖点。"],
            "review_status": "pending_manual_review",
        }
        path = Path("data/runtime/test_template_editor.md")
        write_template_editor_markdown(path, template)
        loaded = load_template_from_markdown(path)

        self.assertEqual(template["id"], loaded["id"])
        self.assertEqual(template["name"], loaded["name"])
        self.assertEqual(template["platforms"], loaded["platforms"])
        self.assertEqual(template["selling_point_order"], loaded["selling_point_order"])
        self.assertEqual(
            template["scene_structure"][0]["role"],
            loaded["scene_structure"][0]["role"],
        )
        path.unlink()

    def test_subtitle_texts_filters_common_ocr_noise(self) -> None:
        items = [
            {"text": "GETREADYWITHBELLE", "confidence": 0.99},
            {"text": "00:00/00:25", "confidence": 0.99},
            {"text": "如果你偏爱舒适体验", "confidence": 0.99},
            {"text": "U果走一整天都不会累", "confidence": 0.99},
            {"text": "D)", "confidence": 0.99},
        ]

        self.assertEqual(
            ["如果你偏爱舒适体验", "如果走一整天都不会累"],
            subtitle_texts(items),
        )


if __name__ == "__main__":
    unittest.main()
