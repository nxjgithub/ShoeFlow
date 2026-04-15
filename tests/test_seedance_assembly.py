import unittest
from pathlib import Path

import cv2
import numpy as np

from gemeiqi.seedance_assembly import assemble_seedance_preview, build_scene_text_maps


class SeedanceAssemblyTests(unittest.TestCase):
    def test_assemble_seedance_preview_creates_fast_cut_manifest(self) -> None:
        base = Path("data/runtime/seedance_assembly_test/downloads")
        processed = base / "processed"
        processed.mkdir(parents=True, exist_ok=True)
        _write_demo_clip(processed / "scene_0001_trimmed.mp4", color=(20, 40, 80))
        _write_demo_clip(processed / "scene_0002_trimmed.mp4", color=(80, 40, 20))

        output = base / "preview.mp4"
        manifest = assemble_seedance_preview(
            download_dir=base,
            output_file=output,
            scene_indexes=[1, 2],
            seconds_per_scene=0.5,
            start_offset_seconds=0.0,
            fps=10.0,
            draw_subtitles=True,
        )

        self.assertTrue(output.exists())
        self.assertTrue(output.with_suffix(".json").exists())
        self.assertTrue(output.with_suffix(".srt").exists())
        self.assertTrue((base / "preview_voiceover.txt").exists())
        self.assertTrue((base / "preview_selection.json").exists())
        self.assertEqual([1, 2], manifest["scene_indexes"])
        self.assertEqual(10, manifest["total_frames"])
        self.assertEqual(1.0, manifest["duration_seconds"])
        self.assertIn("subtitles_file", manifest)
        self.assertIn("voiceover_script_file", manifest)
        self.assertIn("selection_enabled", manifest)
        self.assertIn("selected_start_seconds", manifest["timeline"][0])

    def test_build_scene_text_maps_prefers_script_output_and_links_source_ocr(self) -> None:
        plan = {
            "segments": [
                {
                    "scene_index": 1,
                    "subtitle_suggestion": "plan subtitle",
                    "narration_suggestion": "plan voiceover",
                }
            ]
        }
        script_output = {
            "scenes": [
                {
                    "index": 1,
                    "subtitle_suggestion": "script subtitle",
                    "narration_suggestion": "script voiceover",
                    "source_segment_index": 7,
                    "role": "hook",
                }
            ]
        }
        analysis = {
            "segments": [
                {
                    "index": 7,
                    "ocr_texts": ["hot text a", "hot text b"],
                }
            ]
        }

        subtitle_map, voiceover_map, metadata = build_scene_text_maps(
            plan=plan,
            script_output=script_output,
            analysis=analysis,
            scene_indexes=[1],
        )

        self.assertEqual("script subtitle", subtitle_map[1])
        self.assertEqual("script voiceover", voiceover_map[1])
        self.assertEqual(7, metadata[1]["source_segment_index"])
        self.assertEqual(["hot text a", "hot text b"], metadata[1]["source_ocr_texts"])
        self.assertEqual("hook", metadata[1]["source_role"])


def _write_demo_clip(path: Path, color: tuple[int, int, int]) -> None:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        10.0,
        (64, 96),
    )
    frame = np.zeros((96, 64, 3), dtype=np.uint8)
    frame[:, :] = color
    for _ in range(20):
        writer.write(frame)
    writer.release()
