"""本地 OCR 识别辅助函数。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rapidocr_onnxruntime import RapidOCR


def recognize_images(image_paths: list[Path], min_confidence: float = 0.5) -> list[dict[str, Any]]:
    """识别多张图片中的文字。"""

    engine = RapidOCR()
    results = []
    for image_path in image_paths:
        result, elapsed = engine(str(image_path))
        items = []
        for raw_item in result or []:
            box, text, confidence = raw_item
            if float(confidence) < min_confidence:
                continue
            items.append(
                {
                    "text": str(text),
                    "confidence": round(float(confidence), 4),
                    "box": box,
                }
            )

        results.append(
            {
                "image_path": str(image_path),
                "texts": items,
                "elapsed": elapsed,
            }
        )

    return results


def unique_texts(ocr_items: list[dict[str, Any]]) -> list[str]:
    """按出现顺序返回去重后的 OCR 文本。"""

    texts = []
    seen = set()
    for item in ocr_items:
        text = item["text"].strip()
        if not text or text in seen:
            continue
        texts.append(text)
        seen.add(text)
    return texts


def subtitle_texts(ocr_items: list[dict[str, Any]], min_confidence: float = 0.75) -> list[str]:
    """从 OCR 明细中提取更像字幕或文案的中文候选文本。"""

    candidates = []
    seen = set()
    for item in ocr_items:
        text = _clean_text(item["text"])
        if text in seen:
            continue
        if not _is_useful_subtitle(text=text, confidence=float(item["confidence"])):
            continue
        if float(item["confidence"]) < min_confidence:
            continue
        candidates.append(text)
        seen.add(text)
    return candidates


def _clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("U果", "如果")
    text = text.replace("W果", "如果")
    text = text.replace("W穿脱", "穿脱")
    text = text.replace("W奈脱", "穿脱")
    text = text.replace("文省心", "又省心")
    text = text.replace("义省心", "又省心")
    return text


def _is_useful_subtitle(text: str, confidence: float) -> bool:
    if confidence <= 0:
        return False
    if len(text) < 2:
        return False
    if re.fullmatch(r"[0-9:/：.]+", text):
        return False
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    if len(chinese_chars) < 2:
        return False
    return True
