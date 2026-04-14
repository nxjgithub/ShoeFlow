"""轻量 .env 加载器。"""

from __future__ import annotations

import os
from pathlib import Path

from gemeiqi.paths import project_path


def load_project_env(env_path: Path | None = None) -> Path | None:
    """从项目根目录加载 .env 到当前进程环境变量。"""

    path = env_path or project_path(".env")
    if not path.exists():
        return None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value
    return path
