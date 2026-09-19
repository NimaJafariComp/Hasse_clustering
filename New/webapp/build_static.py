"""Create the deployable static Hasse clustering site.

Run from the repository root:

    python3 New/webapp/build_static.py

The generated ``New/webapp/dist/`` directory is intentionally ignored by Git.
It contains no server code, uploaded user data, or generated clustering output.
"""

from __future__ import annotations

import shutil
from pathlib import Path


WEBAPP_DIR = Path(__file__).resolve().parent
NEW_DIR = WEBAPP_DIR.parent
DIST_DIR = WEBAPP_DIR / "dist"
STATIC_SOURCE_DIR = WEBAPP_DIR / "static"

STATIC_FILES = (
    "app.js",
    "browser-limits.mjs",
    "cluster-worker.mjs",
    "style.css",
)
PYTHON_FILES = ("engine.py", "input_loader.py")


def copy_file(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"Required build input is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def build() -> Path:
    # This script owns only this exact generated directory; never accept a
    # caller-provided deletion target.
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)

    copy_file(STATIC_SOURCE_DIR / "index.html", DIST_DIR / "index.html")
    for name in STATIC_FILES:
        copy_file(STATIC_SOURCE_DIR / name, DIST_DIR / "static" / name)
    for name in PYTHON_FILES:
        copy_file(NEW_DIR / name, DIST_DIR / "python" / name)

    return DIST_DIR


if __name__ == "__main__":
    print(f"Built static site: {build()}")
