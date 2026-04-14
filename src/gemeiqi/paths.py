"""项目路径辅助函数。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = DATA_DIR / "outputs"
EXAMPLES_DIR = PROJECT_ROOT / "examples"
FIXTURES_DIR = EXAMPLES_DIR / "fixtures"


def project_path(*parts: str) -> Path:
    """返回项目根目录下的路径。"""

    return PROJECT_ROOT.joinpath(*parts)


def ensure_output_dir(*parts: str) -> Path:
    """创建并返回 data/outputs 下的输出目录。"""

    path = OUTPUTS_DIR.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path
