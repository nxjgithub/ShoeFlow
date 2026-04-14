"""供 CLI 和测试使用的轻量 JSON 读写辅助函数。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """从磁盘读取 UTF-8 JSON。"""

    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def dump_json(path: Path, data: Any) -> None:
    """以稳定格式写入 UTF-8 JSON。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")
