from __future__ import annotations

import json
from pathlib import Path

DEFAULT_START_KEY = "+"
DEFAULT_STOP_KEY = "-"


def load_hotkeys(base_dir: Path) -> tuple[str, str]:
    """Load hotkeys from config/hotkeys.json with safe defaults."""
    config_path = base_dir / "config" / "hotkeys.json"

    if not config_path.exists():
        return DEFAULT_START_KEY, DEFAULT_STOP_KEY

    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return DEFAULT_START_KEY, DEFAULT_STOP_KEY

    start_key = str(data.get("start_key", DEFAULT_START_KEY)).strip() or DEFAULT_START_KEY
    stop_key = str(data.get("stop_key", DEFAULT_STOP_KEY)).strip() or DEFAULT_STOP_KEY

    return start_key, stop_key
